"""
Export reviewer-confirmed detections as a YOLO-format dataset.

Why this exists: the model only knows what it was trained on. Every time a
person confirms a model detection, or draws a region the model missed on the
Report Problem page, NeceCity stores the image + box + class. This script
turns those into YOLO training files so you can retrain on real, local photos
and the model gets better on exactly the kind of image your users upload.

Usage (from the repo root, with the backend's Python environment active and
the database reachable - same env vars as the backend):

    python ml/training/export_feedback.py --out ml/data/feedback_dataset

Then copy the exported images/labels into ml/data/real_dataset/images/train +
labels/train (keep ~15-20% of them in val/), and retrain:

    python ml/training/train.py

Only CONFIRMED detections are exported. Rejected or never-reviewed model
predictions are never used as labels (they could be wrong).
"""
import argparse
import shutil
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.db.session import SessionLocal  # noqa: E402
from app.ml.classes import load_class_index  # noqa: E402
from app.models.detection import Detection  # noqa: E402
from app.models.enums import DetectionStatus  # noqa: E402
from app.models.image import Image  # noqa: E402


def export(db: Session, out_dir: Path) -> tuple[int, int]:
    class_to_id = {pt.value: idx for idx, pt in load_class_index().items()}
    images_dir, labels_dir = out_dir / "images", out_dir / "labels"
    images_dir.mkdir(parents=True, exist_ok=True)
    labels_dir.mkdir(parents=True, exist_ok=True)

    rows = db.execute(
        select(Detection, Image)
        .join(Image, Detection.image_id == Image.id)
        .where(Detection.status == DetectionStatus.CONFIRMED)
        .order_by(Detection.image_id)
    ).all()

    per_image: dict[int, list[Detection]] = defaultdict(list)
    image_by_id: dict[int, Image] = {}
    for det, img in rows:
        per_image[img.id].append(det)
        image_by_id[img.id] = img

    n_images = n_boxes = 0
    for image_id, dets in per_image.items():
        src = Path(image_by_id[image_id].file_path)
        if not src.exists():
            print(f"skip image {image_id}: file missing at {src}")
            continue
        stem = f"feedback_{image_id}"
        shutil.copy2(src, images_dir / f"{stem}{src.suffix}")

        lines = []
        for d in dets:
            cx = (d.bbox_x_min + d.bbox_x_max) / 2
            cy = (d.bbox_y_min + d.bbox_y_max) / 2
            w = d.bbox_x_max - d.bbox_x_min
            h = d.bbox_y_max - d.bbox_y_min
            lines.append(f"{class_to_id[d.problem_type.value]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")
        (labels_dir / f"{stem}.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
        n_images += 1
        n_boxes += len(lines)
    return n_images, n_boxes


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", default=str(REPO_ROOT / "ml" / "data" / "feedback_dataset"))
    args = parser.parse_args()

    with SessionLocal() as session:
        images, boxes = export(session, Path(args.out))
    print(f"Exported {boxes} labelled box(es) across {images} image(s) to {args.out}")
