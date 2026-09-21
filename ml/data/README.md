# NeceCity Dataset Guide

## DEMO DATA vs REAL TRAINING DATA - read this first

`ml/data/demo_dataset/` contains a **small, synthetic, programmatically
generated** set of placeholder images (flat road-colored backgrounds with
drawn shapes standing in for problems). It exists **only** to let you:

- run `ml/training/train.py` once, end-to-end, as a pipeline smoke test,
- exercise `ml/data/validate_dataset.py` and the dataset folder structure,
- see the backend's Inspect & Analyze flow work end-to-end without first
  collecting real photographs.

**A model trained only on `demo_dataset` will not usefully detect real
infrastructure problems.** It has learned to recognize flat-colored
shapes, not potholes. Treat any metrics from it as a pipeline sanity
check, never as a real accuracy claim - see `ml/weights/README.md`.

To get a real, useful model, replace `demo_dataset` with real annotated
street images following the steps below.

## 1. Classes

Defined once in `ml/data/classes.yaml` (also the file the backend reads
at runtime, so training and serving never disagree about what class 0
means):

| ID | Class | Notes |
|----|-------|-------|
| 0 | pothole | A depression/hole in the road surface |
| 1 | road_damage | Cracking/crumbling not classified as a discrete pothole |
| 2 | garbage | Dumped solid waste on a street/footpath/drain |
| 3 | waterlogging | Standing/pooled water on a road or footpath |
| 4 | damaged_road_sign | Bent, faded, broken or fallen road sign |
| 5 | open_drain | A drain/culvert missing its cover |

If six classes turns out to be too large a labeling burden to finish in
time, the documented fallback is to drop to the 3 most visually distinct
and highest-impact classes: **pothole, garbage, waterlogging** - update
`classes.yaml`, `dataset.yaml`, and `backend/app/models/enums.py`'s
`ProblemType` together, and record the decision here.

## 2. Collecting real images

Free/open sources, in order of recommended effort:

1. **Your own photos.** Walking/cycling around your city with a phone
   camera is the most reliable way to get correctly-labeled, geographically
   relevant data for the classes above. Aim for variety: different times
   of day, weather, distances, and angles.
2. **Openly-licensed image datasets** (e.g. road-damage / pothole
   datasets released for academic research under CC or similar licenses)
   can supplement your own photos, provided the license permits reuse and
   you cite the source in this file once you add any.
3. Do **not** scrape images without checking their license, and do not
   present someone else's copyrighted photography as your own collected
   data.

A realistic minor-project target is **150-400 images per class**
(fewer if you reduce to 3 classes). More is better, but a smaller,
clean, correctly-labeled set beats a larger noisy one.

## 3. Annotating (drawing bounding boxes)

Use a free, offline-capable annotation tool - these are labeling UIs
only, not object-detection services, so they do not conflict with the
project's "no external AI API" rule:

- **[LabelImg](https://github.com/HumanSignal/labelImg)** - simple
  desktop app, exports directly to YOLO `.txt` format.
- **[CVAT](https://github.com/opencv/cvat)** - more capable, can run
  locally via Docker; also exports YOLO format.
- **[makesense.ai](https://www.makesense.ai/)** - runs entirely in your
  browser (no upload to a server), free, exports YOLO format.

For each image, draw one bounding box per visible problem instance and
assign it the correct class. Guidelines:

- Box tightly around the visible extent of the problem, not the whole road.
- If a problem is partially occluded, box the visible portion.
- Skip images where the problem is not clearly identifiable even to a
  human - don't force a label.
- Keep a consistent standard across the dataset (write down your own
  edge-case rules here as you annotate, e.g. "a crack under 5cm wide is
  not `road_damage`").

## 4. Label format (YOLO `.txt`)

One `.txt` file per image, same filename stem, one line per object:

```
<class_id> <x_center> <y_center> <width> <height>
```

All four coordinates are **normalized to [0, 1]** relative to image
width/height. Example (`pothole` roughly centered, covering ~20% of the
frame):

```
0 0.482113 0.611204 0.203981 0.157320
```

Run `python ml/data/validate_dataset.py --dataset <your_dataset_folder>`
after annotating to catch structural mistakes before training.

## 5. Splitting train/val/test

`ml/configs/training_config.yaml` documents the target split
(70% train / 20% val / 10% test). A simple, reproducible way to split:

```bash
# from ml/data/
python - <<'PY'
import random, shutil
from pathlib import Path

random.seed(42)
SRC = Path("my_raw_dataset")           # flat folder: images + matching .txt labels
DST = Path("nececity_dataset")
images = sorted((SRC).glob("*.jpg")) + sorted((SRC).glob("*.png"))
random.shuffle(images)

n = len(images)
splits = {"train": images[:int(n*0.7)], "val": images[int(n*0.7):int(n*0.9)], "test": images[int(n*0.9):]}
for split, files in splits.items():
    (DST / "images" / split).mkdir(parents=True, exist_ok=True)
    (DST / "labels" / split).mkdir(parents=True, exist_ok=True)
    for img in files:
        shutil.copy(img, DST / "images" / split / img.name)
        label = img.with_suffix(".txt")
        if label.exists():
            shutil.copy(label, DST / "labels" / split / label.name)
print({k: len(v) for k, v in splits.items()})
PY
```

(The `test` split isn't wired into `ml/training/dataset.yaml`'s `val:`
key by default - use it as a final, only-once check with
`ml/evaluation/evaluate.py --split test` after you've stopped tuning.)

## 6. From-scratch vs. transfer learning

The project documentation asks that this be explicit and never
misrepresented:

- **What NeceCity trains itself:** all of the detection head's learned
  weights for these 6 specific classes, on NeceCity's own dataset. Class
  definitions, data collection, annotation, the train/val/test split, the
  training run, and the resulting weights are entirely project-owned.
- **What is reused (if `initialization: pretrained` in
  `ml/configs/model_config.yaml`):** the YOLOv8n backbone's general
  low-level visual features (edges, textures, shapes), initialized from
  weights pretrained on the public COCO dataset by the Ultralytics/YOLO
  open-source project - not from any paid or hosted API.
- Why this is recommended: with a few hundred images per class (typical
  for a minor project), training entirely from random initialization
  usually needs far more data and epochs to converge to a usable model.
  Transfer learning lets the small dataset focus on *learning what a
  pothole looks like* rather than also *relearning what an edge is*.
- `ml/configs/model_config.yaml` also documents `initialization: random`
  for a genuine from-scratch run if you have the data/compute and want to
  compare - be prepared to explain the accuracy difference in your viva.

## 7. Reproducing this synthetic demo dataset

`scripts/generate_demo_dataset.py` (repository root) generates the
placeholder images described at the top of this file. Re-run it any time
with `python scripts/generate_demo_dataset.py` - it's deterministic
(fixed random seed) and safe to regenerate.
