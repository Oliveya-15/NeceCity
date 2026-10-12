#!/usr/bin/env python3
r"""
Prepares a real-photo dataset for training, without you having to
manually create folders or drag files around.

WHAT IT DOES:
Takes a single flat folder where you've dropped your photos + the
matching .txt label file makesense.ai exported for each one, and
automatically sorts them into the images/train, images/val,
labels/train, labels/val structure that ml/training/dataset.yaml
expects.

The split is CLASS-STRATIFIED, not purely random: it reads which
classes actually appear in each label file first, then guarantees every
class that has more than one example gets at least one representative in
the validation set. With a small dataset (a handful of images per
class), a plain random split can easily leave a class with ZERO
validation images by chance - when that happens, evaluate.py can only
report "no validation instances for this class" for it, which looks like
a bug but is really a sampling accident. Stratifying avoids that.

BEFORE RUNNING THIS:
1. Take your real photos (see ml/data/README.md).
2. Annotate them at https://www.makesense.ai/ and export as "YOLO".
3. Put every image AND its matching .txt file (same filename, different
   extension) into one flat folder.

USAGE (from ml/data/):
    python prepare_real_dataset.py --source C:\Work\my_photos --dest real_dataset

Then point ml/training/dataset_real.yaml's `path:` at ../data/real_dataset
and train with: python train.py --dataset dataset_real.yaml
"""
import argparse
import random
import shutil
from collections import defaultdict
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def parse_classes(label_path: Path) -> set[int]:
    classes = set()
    for line in label_path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        try:
            classes.add(int(parts[0]))
        except (ValueError, IndexError):
            continue  # malformed lines are reported by validate_dataset.py, not here
    return classes


def stratified_split(paired: list[tuple[Path, Path, set[int]]], val_ratio: float, rng: random.Random):
    """
    Returns (train_set, val_set) as lists of (image_path, label_path).
    Guarantees every class with 2+ total images gets >=1 val image.
    """
    rng.shuffle(paired)

    class_to_images: dict[int, list[int]] = defaultdict(list)  # class_id -> indices into `paired`
    for idx, (_, _, classes) in enumerate(paired):
        for c in classes:
            class_to_images[c].append(idx)

    val_indices: set[int] = set()
    covered_classes: set[int] = set()

    # Process rarest classes first, so a scarce class doesn't lose its one
    # shot at val coverage to a more common class grabbing the same image.
    for class_id in sorted(class_to_images, key=lambda c: len(class_to_images[c])):
        if class_id in covered_classes:
            continue
        candidates = class_to_images[class_id]
        if len(candidates) < 2:
            continue  # only one example total - keep it in train, or the model never sees it at all
        pick = next((i for i in candidates if i not in val_indices), None)
        if pick is None:
            pick = rng.choice(candidates)
        val_indices.add(pick)
        covered_classes.update(paired[pick][2])

    target_val_count = max(len(val_indices), round(len(paired) * val_ratio))
    remaining = [i for i in range(len(paired)) if i not in val_indices]
    rng.shuffle(remaining)
    for i in remaining:
        if len(val_indices) >= target_val_count:
            break
        val_indices.add(i)

    train_set = [(paired[i][0], paired[i][1]) for i in range(len(paired)) if i not in val_indices]
    val_set = [(paired[i][0], paired[i][1]) for i in sorted(val_indices)]
    return train_set, val_set


def main():
    parser = argparse.ArgumentParser(description="Split a flat folder of labeled photos into train/val.")
    parser.add_argument("--source", required=True, help="Folder containing your images + matching .txt labels.")
    parser.add_argument("--dest", default="real_dataset", help="Output dataset folder (created if missing).")
    parser.add_argument("--val-ratio", type=float, default=0.2, help="Target fraction of images held out for validation.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed, so re-running gives the same split.")
    args = parser.parse_args()

    source = Path(args.source)
    dest = Path(args.dest)

    if not source.exists():
        raise SystemExit(f"Source folder not found: {source}")

    images = sorted(p for p in source.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
    if not images:
        raise SystemExit(f"No .jpg/.jpeg/.png images found in {source}")

    paired: list[tuple[Path, Path, set[int]]] = []
    skipped = []
    for img in images:
        label = img.with_suffix(".txt")
        if not label.exists():
            skipped.append(img.name)
            continue
        classes = parse_classes(label)
        if not classes:
            skipped.append(f"{img.name} (label file has no valid annotations)")
            continue
        paired.append((img, label, classes))

    if skipped:
        print(f"WARNING: {len(skipped)} image(s) skipped (no usable label):")
        for name in skipped:
            print(f"  - {name}")

    if len(paired) < 2:
        raise SystemExit(f"Only {len(paired)} labeled image(s) found - need at least 2.")

    rng = random.Random(args.seed)
    train_set, val_set = stratified_split(paired, args.val_ratio, rng)

    for split_name, split_pairs in [("train", train_set), ("val", val_set)]:
        images_dir = dest / "images" / split_name
        labels_dir = dest / "labels" / split_name
        images_dir.mkdir(parents=True, exist_ok=True)
        labels_dir.mkdir(parents=True, exist_ok=True)
        for img, label in split_pairs:
            shutil.copy2(img, images_dir / img.name)
            shutil.copy2(label, labels_dir / label.name)

    # Per-class coverage report - so you can SEE the balance, not just hope for it.
    def count_per_class(split_pairs):
        counts: dict[int, int] = defaultdict(int)
        for _, label in split_pairs:
            for c in parse_classes(label):
                counts[c] += 1
        return counts

    train_counts = count_per_class(train_set)
    val_counts = count_per_class(val_set)
    all_classes = sorted(set(train_counts) | set(val_counts))

    print(f"\nDone: {len(train_set)} training image(s), {len(val_set)} validation image(s).")
    print(f"Dataset written to: {dest.resolve()}\n")
    print(f"{'Class':>6}  {'Train':>6}  {'Val':>6}")
    for c in all_classes:
        flag = "  <- NO VAL EXAMPLES" if val_counts.get(c, 0) == 0 else ""
        print(f"{c:>6}  {train_counts.get(c, 0):>6}  {val_counts.get(c, 0):>6}{flag}")
    print(f"\nNext: point ml/training/dataset_real.yaml's 'path:' at this folder, then run train.py --dataset dataset_real.yaml")


if __name__ == "__main__":
    main()