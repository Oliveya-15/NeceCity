#!/usr/bin/env python3
"""
NeceCity model training script.

Trains a YOLO object detector on the NeceCity dataset (see
ml/training/dataset.yaml) using Ultralytics YOLO, starting from either:

  - COCO-pretrained weights (transfer learning, recommended - see
    ml/configs/model_config.yaml `initialization: pretrained`), or
  - random initialization (`initialization: random`), if you specifically
    want to train from scratch and have enough data/compute to justify it.

Usage:
    cd ml/training
    python train.py
    python train.py --config ../configs/training_config.yaml --dataset dataset.yaml

Runs equally well on a local machine (CPU or GPU) or in Google Colab (see
notebooks/NeceCity_Training_Colab.ipynb for a ready-to-run Colab version
of these same steps).

Output: trained weights are saved by Ultralytics under
`runs/detect/<run_name>/weights/best.pt`. Copy that file to
`ml/weights/nececity_yolo.pt` (see ml/weights/README.md) for the backend
to pick it up.
"""
import argparse
import json
from datetime import datetime
from pathlib import Path

import ultralytics
import yaml


def load_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    parser = argparse.ArgumentParser(description="Train the NeceCity YOLO detector.")
    parser.add_argument("--config", default="../configs/training_config.yaml")
    parser.add_argument("--model-config", default="../configs/model_config.yaml")
    parser.add_argument("--dataset", default="dataset.yaml")
    args = parser.parse_args()

    training_cfg = load_yaml(args.config)
    model_cfg = load_yaml(args.model_config)

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit(
            "ultralytics/torch are not installed. Run:\n"
            "  pip install -r ../requirements.txt\n"
            "(or open notebooks/NeceCity_Training_Colab.ipynb to train on a free Colab GPU instead.)"
        ) from exc

    initialization = model_cfg["initialization"]
    if initialization == "pretrained":
        weights_seed = model_cfg["pretrained_weights"]
        print(f"[NeceCity] Starting from COCO-pretrained weights: {weights_seed} (transfer learning).")
    elif initialization == "random":
        # Passing the .yaml architecture definition (instead of a .pt file)
        # tells ultralytics to build the network with randomly initialized
        # weights rather than loading any pretrained checkpoint.
        weights_seed = f"{model_cfg['architecture']}.yaml"
        print(f"[NeceCity] Starting from RANDOM initialization: {weights_seed} (training from scratch).")
    else:
        raise ValueError(f"Unknown initialization mode '{initialization}' in model_config.yaml")

    model = YOLO(weights_seed)

    aug = training_cfg.get("augmentation", {})
    results = model.train(
        data=args.dataset,
        epochs=training_cfg["epochs"],
        batch=training_cfg["batch_size"],
        imgsz=training_cfg["image_size"],
        patience=training_cfg["patience"],
        lr0=training_cfg["learning_rate"],
        optimizer=training_cfg["optimizer"],
        seed=training_cfg["seed"],
        workers=training_cfg["workers"],
        name=training_cfg["run_name"],
        degrees=aug.get("degrees", 0.0),
        fliplr=aug.get("fliplr", 0.5),
        flipud=aug.get("flipud", 0.0),
        mosaic=aug.get("mosaic", 1.0),
        mixup=aug.get("mixup", 0.0),
        hsv_h=aug.get("hsv_h", 0.015),
        hsv_s=aug.get("hsv_s", 0.7),
        hsv_v=aug.get("hsv_v", 0.4),
    )

    best_weights = Path(model.trainer.save_dir) / "weights" / "best.pt"

    # Write provenance metadata alongside the weights so the backend (and
    # anyone reading ml/weights/ later) can tell what this checkpoint was
    # actually trained on - critically, whether it used the bundled
    # SYNTHETIC placeholder dataset (ml/data/demo_dataset) rather than
    # real photographs. A model trained only on synthetic shapes will not
    # meaningfully detect real-world objects; this metadata is what lets
    # the app surface that honestly instead of silently returning "no
    # detections" as if something were broken (see project rule: no fake
    # AI capabilities, and app/ml/inference.py which reads this file).
    dataset_path = Path(args.dataset).resolve()
    is_demo_dataset = "demo_dataset" in str(dataset_path)
    metadata = {
        "trained_at": datetime.utcnow().isoformat() + "Z",
        "dataset_path": str(dataset_path),
        "is_bundled_demo_dataset": is_demo_dataset,
        "epochs": training_cfg["epochs"],
        "architecture": model_cfg["architecture"],
        "initialization": initialization,
        "ultralytics_version": ultralytics.__version__,
    }
    # Written directly to ml/weights/ - the same folder best.pt gets
    # copied into - so it's already in place the moment you copy the
    # weights file across (one metadata write per training run; if you
    # retrain before copying an earlier run's weights, this simply
    # reflects the most recent run).
    metadata_path = Path(__file__).resolve().parent.parent / "weights" / "nececity_yolo.meta.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"\n[NeceCity] Training complete.")
    print(f"[NeceCity] Best weights saved at: {best_weights}")
    print(f"[NeceCity] To use them in the backend, copy this file to: ml/weights/nececity_yolo.pt")
    print(f"[NeceCity] (or set MODEL_PATH in your .env to point at it directly)")
    print(f"[NeceCity] Provenance metadata already written to: {metadata_path}")
    if is_demo_dataset:
        print(
            "\n[NeceCity] WARNING: trained on the bundled SYNTHETIC placeholder dataset "
            "(ml/data/demo_dataset). This checkpoint will NOT reliably detect real-world "
            "problems in real photos - see ml/data/README.md to train on real images. "
            "The app will now show this warning automatically in Inspect & Analyze."
        )


if __name__ == "__main__":
    main()
