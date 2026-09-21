#!/usr/bin/env python3
"""
NeceCity model evaluation script.

Runs the trained model against the held-out validation/test split and
reports standard object-detection metrics: precision, recall, mAP@0.5 and
mAP@0.5:0.95, both overall and per-class.

These are the metrics you should report in your viva/documentation -
never hand-write or guess metric numbers (project rule 36: no fake AI /
no fabricated model accuracy).

Usage:
    cd ml/evaluation
    python evaluate.py --weights ../weights/nececity_yolo.pt --dataset ../training/dataset.yaml --split val
"""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description="Evaluate the NeceCity YOLO detector.")
    parser.add_argument("--weights", default="../weights/nececity_yolo.pt")
    parser.add_argument("--dataset", default="../training/dataset.yaml")
    parser.add_argument("--split", default="val", choices=["val", "test"])
    parser.add_argument("--output", default="../weights/evaluation_report.json")
    args = parser.parse_args()

    weights_path = Path(args.weights)
    if not weights_path.exists():
        raise SystemExit(
            f"Weights file not found at '{weights_path}'.\n"
            "Train a model first (python ../training/train.py) or place your "
            "trained .pt file at this path."
        )

    try:
        from ultralytics import YOLO
    except ImportError as exc:
        raise SystemExit("ultralytics/torch are not installed. Run: pip install -r ../requirements.txt") from exc

    model = YOLO(str(weights_path))
    metrics = model.val(data=args.dataset, split=args.split)

    class_names = metrics.names
    per_class = {}
    for idx, name in class_names.items():
        try:
            per_class[name] = {
                "precision": float(metrics.box.p[idx]),
                "recall": float(metrics.box.r[idx]),
                "mAP50": float(metrics.box.ap50[idx]),
                "mAP50_95": float(metrics.box.ap[idx]),
            }
        except (IndexError, TypeError):
            per_class[name] = {"note": "No validation instances for this class - metric undefined."}

    report = {
        "weights": str(weights_path),
        "split": args.split,
        "overall": {
            "precision": float(metrics.box.mp),
            "recall": float(metrics.box.mr),
            "mAP50": float(metrics.box.map50),
            "mAP50_95": float(metrics.box.map),
        },
        "per_class": per_class,
    }

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(json.dumps(report, indent=2))
    print(f"\n[NeceCity] Evaluation report saved to: {args.output}")
    print("[NeceCity] Copy the 'overall' numbers into docs/ml-pipeline.md when you update the model.")


if __name__ == "__main__":
    main()
