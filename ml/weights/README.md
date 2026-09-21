# ml/weights/

Trained model weight files (`.pt`) go here. **This folder is intentionally
empty in the repository** (weight files are large binaries and shouldn't
be committed to Git - see `.gitignore`) except for this README.

## What the backend expects

`backend/.env` sets `MODEL_PATH=../ml/weights/nececity_yolo.pt` by
default. After training (`ml/training/train.py`), copy the best checkpoint
here:

```bash
cp ml/training/runs/detect/nececity_yolo/weights/best.pt ml/weights/nececity_yolo.pt
```

Restart the backend (or just let it reload on next request if running
with `--reload`) and it will pick up the new weights automatically - see
`backend/app/ml/inference.py`.

## If this file is missing

**The application does not crash.** `NeceCityDetector` (in
`backend/app/ml/inference.py`) detects a missing/unloadable weights file
at startup and Inspect & Analyze responds with:

> "ML model is not configured. Add the trained NeceCity model weights and
> configure MODEL_PATH."

Every other page (Command Center, City Monitor, Insights, Action Center)
continues to work normally off the database/demo data, because model
training and web deployment are deliberately separate stages (project
rule 29).

## Evaluation report

`ml/evaluation/evaluate.py` writes `evaluation_report.json` to this
folder with the real precision/recall/mAP50/mAP50-95 numbers for whatever
weights file you point it at. Keep that file alongside the weights it
describes so the numbers in `docs/ml-pipeline.md` can always be traced
back to a specific trained checkpoint.

## Provenance metadata (`nececity_yolo.meta.json`)

Every training run (`ml/training/train.py`) now also writes a small JSON
file here recording what the weights were actually trained on -
critically, whether it was the bundled **synthetic placeholder dataset**
(`ml/data/demo_dataset`, programmatically-drawn shapes) rather than real
photographs. The backend reads this at startup
(`app/ml/inference.py`) and, if it detects a synthetic-only model, shows
a clear warning in Inspect & Analyze and in the always-visible model
status badge - instead of silently returning "nothing detected" and
leaving you to guess whether something is broken.

If you copy in a weights file without its matching `.meta.json` (e.g.
weights trained before this feature existed), the app shows a generic
"provenance unknown" note instead - it still works, it just can't tell
you automatically whether the model saw real images during training.

