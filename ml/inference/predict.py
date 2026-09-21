#!/usr/bin/env python3
"""
Standalone NeceCity inference CLI.

Deliberately independent of backend/app/ml/inference.py (some duplication
is intentional - see project rule 9: "the training pipeline must be
separable from the web application"). This script lets you sanity-check a
trained model directly from the command line, without running the FastAPI
server at all.

Usage:
    python predict.py --weights ../weights/nececity_yolo.pt --source /path/to/image.jpg
    python predict.py --weights ../weights/nececity_yolo.pt --source /path/to/folder/ --save
"""
import argparse
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Run NeceCity YOLO inference on an image or folder.")
    parser.add_argument("--weights", default="../weights/nececity_yolo.pt")
    parser.add_argument("--source", required=True, help="Image file or folder of images.")
    parser.add_argument("--conf", type=float, default=0.35)
    parser.add_argument("--iou", type=float, default=0.45)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--save", action="store_true", help="Save annotated output images.")
    args = parser.parse_args()

    weights_path = Path(args.weights)
    if not weights_path.exists():
        raise SystemExit(f"Weights not found at '{weights_path}'. Train a model first (see ml/training/train.py).")

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("ultralytics/torch are not installed. Run: pip install -r ../requirements.txt") from exc

    model = YOLO(str(weights_path))
    results = model.predict(
        source=args.source, conf=args.conf, iou=args.iou, imgsz=args.imgsz, save=args.save, verbose=True,
    )

    for result in results:
        print(f"\n{result.path}: {len(result.boxes)} detection(s)")
        for box in result.boxes:
            cls_name = result.names[int(box.cls.item())]
            conf = float(box.conf.item())
            x_min, y_min, x_max, y_max = box.xyxyn[0].tolist()
            print(f"  - {cls_name}: confidence={conf:.2f}  bbox=({x_min:.3f}, {y_min:.3f}, {x_max:.3f}, {y_max:.3f})")

    if args.save:
        print("\n[NeceCity] Annotated images saved under runs/detect/predict*/")


if __name__ == "__main__":
    main()
