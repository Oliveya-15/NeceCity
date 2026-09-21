#!/usr/bin/env python3
"""
Validates a YOLO-format dataset's structure and label files WITHOUT
needing torch/ultralytics installed - useful in CI and quick sanity checks
before kicking off an expensive training run.

Checks:
  - every image has a matching .txt label file (and vice versa)
  - every label line has exactly 5 whitespace-separated values
  - class_id is an integer within [0, num_classes)
  - the 4 bbox values are normalized floats within [0, 1]

Usage:
    python validate_dataset.py --dataset demo_dataset --classes classes.yaml
"""
import argparse
import sys
from pathlib import Path

import yaml

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


def validate_split(images_dir: Path, labels_dir: Path, num_classes: int, split_name: str) -> list[str]:
    errors: list[str] = []

    if not images_dir.exists():
        return [f"[{split_name}] images directory not found: {images_dir}"]

    image_files = sorted(p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS)
    if not image_files:
        errors.append(f"[{split_name}] no images found in {images_dir}")

    for image_path in image_files:
        label_path = labels_dir / (image_path.stem + ".txt")
        if not label_path.exists():
            errors.append(f"[{split_name}] missing label file for {image_path.name}")
            continue

        lines = [ln for ln in label_path.read_text().splitlines() if ln.strip()]
        if not lines:
            errors.append(f"[{split_name}] {label_path.name} is empty (no annotated objects)")
            continue

        for i, line in enumerate(lines, start=1):
            parts = line.split()
            if len(parts) != 5:
                errors.append(f"[{split_name}] {label_path.name} line {i}: expected 5 values, got {len(parts)}")
                continue
            try:
                class_id = int(parts[0])
                coords = [float(x) for x in parts[1:]]
            except ValueError:
                errors.append(f"[{split_name}] {label_path.name} line {i}: non-numeric value")
                continue

            if not (0 <= class_id < num_classes):
                errors.append(f"[{split_name}] {label_path.name} line {i}: class_id {class_id} out of range [0, {num_classes})")
            if any(not (0.0 <= c <= 1.0) for c in coords):
                errors.append(f"[{split_name}] {label_path.name} line {i}: bbox coords must be normalized to [0, 1]")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a YOLO-format NeceCity dataset.")
    parser.add_argument("--dataset", default="demo_dataset", help="Path to the dataset root (contains images/, labels/).")
    parser.add_argument("--classes", default="classes.yaml")
    args = parser.parse_args()

    dataset_root = Path(args.dataset)
    classes_path = Path(args.classes)

    with open(classes_path, "r", encoding="utf-8") as f:
        classes_data = yaml.safe_load(f)
    num_classes = len(classes_data["names"])

    all_errors = []
    for split in ["train", "val"]:
        all_errors += validate_split(
            dataset_root / "images" / split, dataset_root / "labels" / split, num_classes, split
        )

    if all_errors:
        print(f"FAILED: {len(all_errors)} issue(s) found:\n")
        for err in all_errors:
            print(f"  - {err}")
        return 1

    print(f"OK: dataset at '{dataset_root}' is structurally valid ({num_classes} classes).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
