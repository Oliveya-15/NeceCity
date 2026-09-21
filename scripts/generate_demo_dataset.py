#!/usr/bin/env python3
"""
Generates a SMALL, SYNTHETIC, CLEARLY-FAKE placeholder dataset under
ml/data/demo_dataset/.

WHY THIS EXISTS: the project must distinguish DEMO DATA from REAL
TRAINING DATA at all times (project rule 7). These images are simple
programmatically-drawn shapes on flat backgrounds - they exist ONLY so
that:
  - the dataset folder structure and dataset.yaml can be exercised/tested,
  - ml/data/validate_dataset.py has something concrete to validate,
  - `python train.py` can be run once as an end-to-end pipeline smoke
    test (verifying the code runs, NOT that it produces a usable model).

They are NOT real street photographs and a model trained only on this
data will NOT be able to detect real-world infrastructure problems. See
ml/data/README.md for exactly how to replace this with a real annotated
dataset.
"""
import random
from pathlib import Path

from PIL import Image, ImageDraw

random.seed(7)

ROOT = Path(__file__).resolve().parent.parent / "ml" / "data" / "demo_dataset"
IMG_SIZE = (640, 480)

# class_id: (name, fill_color, shape)
CLASSES = {
    0: ("pothole", (40, 40, 40), "ellipse"),
    1: ("road_damage", (90, 70, 50), "polygon"),
    2: ("garbage", (120, 150, 40), "scatter"),
    3: ("waterlogging", (60, 110, 180), "rect"),
    4: ("damaged_road_sign", (200, 60, 60), "rect"),
    5: ("open_drain", (20, 20, 20), "rect"),
}

ROAD_COLORS = [(105, 105, 108), (96, 94, 90), (112, 110, 106)]


def draw_object(draw: ImageDraw.ImageDraw, class_id: int, box):
    x_min, y_min, x_max, y_max = box
    _, color, shape = CLASSES[class_id]
    if shape == "ellipse":
        draw.ellipse(box, fill=color)
    elif shape == "rect":
        draw.rectangle(box, fill=color)
    elif shape == "polygon":
        draw.polygon(
            [(x_min, y_max), (x_min + (x_max - x_min) * 0.3, y_min), (x_max, y_min + (y_max - y_min) * 0.4), (x_max, y_max)],
            fill=color,
        )
    elif shape == "scatter":
        for _ in range(6):
            cx = random.uniform(x_min, x_max)
            cy = random.uniform(y_min, y_max)
            r = random.uniform(6, 14)
            draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)


def generate_image(image_id: int, split: str):
    img = Image.new("RGB", IMG_SIZE, random.choice(ROAD_COLORS))
    draw = ImageDraw.Draw(img)
    # A simple horizon line + lane marking so it vaguely reads as "a road".
    draw.rectangle([0, 0, IMG_SIZE[0], IMG_SIZE[1] * 0.35], fill=(190, 200, 210))
    draw.rectangle([IMG_SIZE[0] * 0.48, IMG_SIZE[1] * 0.4, IMG_SIZE[0] * 0.52, IMG_SIZE[1]], fill=(230, 210, 90))

    num_objects = random.randint(1, 2)
    labels = []
    used_classes = random.sample(list(CLASSES.keys()), k=num_objects)
    for class_id in used_classes:
        w = random.uniform(0.12, 0.28) * IMG_SIZE[0]
        h = random.uniform(0.10, 0.22) * IMG_SIZE[1]
        cx = random.uniform(0.15, 0.85) * IMG_SIZE[0]
        cy = random.uniform(0.45, 0.85) * IMG_SIZE[1]
        box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
        draw_object(draw, class_id, box)

        x_center = (box[0] + box[2]) / 2 / IMG_SIZE[0]
        y_center = (box[1] + box[3]) / 2 / IMG_SIZE[1]
        norm_w = w / IMG_SIZE[0]
        norm_h = h / IMG_SIZE[1]
        labels.append(f"{class_id} {x_center:.6f} {y_center:.6f} {norm_w:.6f} {norm_h:.6f}")

    img_path = ROOT / "images" / split / f"demo_{image_id:03d}.jpg"
    label_path = ROOT / "labels" / split / f"demo_{image_id:03d}.txt"
    img.save(img_path, quality=85)
    label_path.write_text("\n".join(labels) + "\n")


def main():
    for split, count in [("train", 16), ("val", 6)]:
        for i in range(count):
            generate_image(i, split)
    print(f"Generated synthetic demo dataset at {ROOT}")


if __name__ == "__main__":
    main()
