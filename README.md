# NeceCity

**AI-powered urban infrastructure monitoring & decision-support system.**

NeceCity detects urban infrastructure problems (potholes, road damage,
garbage, waterlogging, damaged signage, open drains) from street-level
photographs using a project-owned, locally-trained YOLO computer vision
model, combines detections with geographic and historical data, computes
an explainable risk/priority score, and helps a city track problems from
detection through resolution.

This is the **current minor-project version**: six working sections
(Command Center, City Monitor, Inspect & Analyze, Insights, Action
Center, AI Recommendations), a real PostgreSQL/PostGIS database, a real
FastAPI backend, a real React frontend, and a real (separately
trainable) ML pipeline - built to be demoed, explained in a viva, and
extended later.

**For a full architecture walkthrough (tech stack rationale, core
problems & solutions, and an explicit map of exactly where every number
on screen comes from), see [`ARCHITECTURE.md`](ARCHITECTURE.md).**

---

## 1. What NeceCity is

A city-agnostic (not hard-coded to one city) web application that turns
"someone photographed a pothole" into "the municipality knows exactly
where its highest-risk infrastructure problems are and what to do about
them first" - combining Computer Vision, Data Science, Geospatial
Analysis and a rule-based decision-support engine.

## 2. Problem statement

Municipalities typically learn about infrastructure problems reactively
(complaints, news reports) with no systematic way to compare severity
across locations or verify what's already been reported. NeceCity gives
a structured pipeline: **see the problem -> understand it -> analyze the
pattern -> calculate risk -> prioritize -> recommend an action -> track
status.**

## 3. Features

| Section | What it does |
|---|---|
| **Command Center** | City-wide overview: totals, severity/status/type breakdowns, infrastructure health score, top priorities, recent critical detections. |
| **City Monitor** | Interactive Leaflet/OpenStreetMap map with type/severity/status/ward/date filters and a location detail panel. |
| **Inspect & Analyze** | Upload a street photo -> local YOLO inference -> bounding boxes + confidence + suggested severity -> human Confirm/Reject/Edit Severity -> becomes a tracked Problem. |
| **Insights** | Real Data Science analytics: distribution by type/severity/area, time trends (pandas), DBSCAN hotspot clustering (scikit-learn), recurring-problem detection, deterministic "Data Insight" statements. |
| **Action Center** | Explainable risk-ranked priority queue, problem lifecycle (Detected -> Verified -> In Progress -> Resolved), PDF/CSV reporting. |
| **AI Recommendations** | Chat with an assistant grounded in your city's real data (LLM-backed if you configure an API key, otherwise a data-grounded rule-based assistant - works either way), alongside a directory of verified real civic organizations and general awareness tips. |

## 4. Architecture

```
Browser (React + Leaflet + Recharts)
        │  REST/JSON (+ multipart upload)
        ▼
FastAPI backend  ──►  app/ml       (YOLO inference, local, no external API)
                 ──►  app/risk     (explainable weighted risk engine)
                 ──►  app/analytics(pandas / scikit-learn Data Science)
                 ──►  app/services (business logic, separate from routes)
        │  SQLAlchemy + GeoAlchemy2
        ▼
PostgreSQL + PostGIS  (cities, wards, locations, images, detections,
                        problems, risk_scores, resolutions)

ml/  (training/evaluation/inference - separable from the web app;
      runs locally or on Google Colab; produces the .pt weights file
      the backend loads)
```

Full detail: [`docs/architecture.md`](docs/architecture.md).

## 5. Tech stack (and exactly why each piece is used)

| Layer | Technology | Used for |
|---|---|---|
| ML/CV | Python, PyTorch, Ultralytics YOLOv8, OpenCV | Training/running the object detector |
| Data Science | Pandas, NumPy, scikit-learn, GeoPandas | Trend analysis, DBSCAN hotspot clustering, spatial preprocessing |
| Backend | FastAPI | REST API + serving the ML model |
| Database | PostgreSQL + PostGIS | Relational data + real spatial queries (`ST_DWithin`, GIST indexes) |
| Frontend | React + Tailwind CSS | UI |
| Map | Leaflet + OpenStreetMap | Free interactive mapping, no paid API |
| Charts | Recharts | Distribution/trend visualization |
| Reporting | ReportLab (PDF), CSV | Action Center exports |
| Containerization | Docker + Docker Compose | Reproducible local/deployment environment |

No paid API is required anywhere in this stack.

## 6. Project structure

```
nececity/
├── backend/          FastAPI app, SQLAlchemy models, Alembic migrations, tests
│   └── app/
│       ├── api/routes/    thin route handlers only
│       ├── services/      business logic
│       ├── analytics/     Data Science (Insights page)
│       ├── risk/          explainable risk engine (Action Center)
│       ├── ml/            inference service (graceful degradation)
│       └── seed/          demo/seed data generator
├── ml/               Training pipeline - separable from the web app
│   ├── data/         classes.yaml, dataset docs, demo dataset, validator
│   ├── training/      train.py, dataset.yaml
│   ├── evaluation/    evaluate.py (real precision/recall/mAP)
│   ├── inference/      standalone predict.py CLI
│   ├── configs/        model_config.yaml, training_config.yaml
│   └── weights/         trained .pt file goes here (gitignored)
├── notebooks/         Google Colab training notebook
├── frontend/          React + Vite + Tailwind
├── scripts/           utility scripts (e.g. demo dataset generator)
├── docs/              architecture, setup, database, ml-pipeline, dataset, api, roadmap
├── docker-compose.yml
└── .env.example
```

## 7. Prerequisites

Install on your machine:

- **Git**
- **Python 3.11+**
- **Node.js 20+** and npm
- **Docker Desktop** (recommended path - runs Postgres/PostGIS for you)
- **PostgreSQL 16 + PostGIS 3** if you'd rather run the database outside Docker
- Optional: an NVIDIA GPU + CUDA for faster local model training (not required - CPU works, and Google Colab provides a free GPU)
- A Google account only if you choose to train the model on Google Colab

## 8. Local setup (Windows-friendly - run each block in the terminal named)

### Fastest path: Docker Compose (runs database + backend + frontend)

**PowerShell, in the project root:**
```powershell
copy .env.example .env
docker compose up --build
```
Then open **http://localhost:8080** (frontend) - the backend API is at
`http://localhost:8000/api/v1`. The backend container runs migrations and
seeds demo data automatically on first start.

### Manual path (more control, e.g. while developing)

**PowerShell - start the database (skip if you have Postgres+PostGIS installed natively):**
```powershell
docker run -d --name nececity-db -e POSTGRES_USER=nececity -e POSTGRES_PASSWORD=nececity -e POSTGRES_DB=nececity -p 5432:5432 postgis/postgis:16-3.4
```

**Backend terminal:**
```powershell
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m alembic upgrade head
python -m app.seed.seed_data
uvicorn app.main:app --reload
```
Backend now running at http://localhost:8000 (docs at `/docs`).

**Frontend terminal:**
```powershell
cd frontend
npm install
copy .env.example .env
npm run dev
```
Frontend now running at http://localhost:5173.

## 9. Environment variables

See [`backend/.env.example`](backend/.env.example),
[`frontend/.env.example`](frontend/.env.example), and
[`.env.example`](.env.example) (Docker Compose level). Every variable is
documented inline. Nothing is hard-coded; no secrets are committed.

## 10. Database setup

Migrations are managed with Alembic (`backend/alembic/`). The schema
(`cities`, `wards`, `locations`, `images`, `detections`, `problems`,
`risk_scores`, `resolutions`) uses real PostGIS `Geometry` columns and
GIST spatial indexes - see [`docs/database.md`](docs/database.md) for the
full entity-relationship explanation and why PostGIS is needed at all.

```powershell
cd backend
python -m alembic upgrade head      # apply migrations
python -m app.seed.seed_data        # load demo data (add --reset to wipe and regenerate)
```

## 11. Docker setup

```powershell
docker compose up --build
```
Services: `database` (postgis/postgis:16-3.4), `backend` (FastAPI, runs
migrations+seed on start), `frontend` (nginx serving the built React app).
See `docker-compose.yml` - every value is either a sane default or read
from `.env`.

## 12. Dataset setup / 13. Annotation / 14. Model training / 15. Evaluation / 16. Weight placement / 17. Running inference

All covered in depth in [`ml/data/README.md`](ml/data/README.md) (dataset
& annotation) and [`ml/weights/README.md`](ml/weights/README.md) (weight
placement). Quick version:

```powershell
cd ml
pip install -r requirements.txt
python data/validate_dataset.py --dataset data/demo_dataset --classes data/classes.yaml

cd training
python train.py                     # trains YOLOv8n, transfer learning by default

cd ..\evaluation
python evaluate.py --weights ..\training\runs\detect\nececity_yolo\weights\best.pt --dataset ..\training\dataset.yaml

copy ..\training\runs\detect\nececity_yolo\weights\best.pt ..\weights\nececity_yolo.pt
```
Restart the backend and Inspect & Analyze will use the new weights.
Training on **Google Colab** instead: open
[`notebooks/NeceCity_Training_Colab.ipynb`](notebooks/NeceCity_Training_Colab.ipynb).

**Important:** the bundled `ml/data/demo_dataset/` is **synthetic
placeholder data** (programmatically drawn shapes), only for testing the
pipeline mechanics - see the big warning at the top of
`ml/data/README.md` before you assume it trains a real detector.

## 18. Running frontend/backend

Covered in section 8 above.

For Everytime : docker compose up --build
Once you see Uvicorn running on http://0.0.0.0:8000, open:

http://localhost:8080 — the app
http://localhost:8000/docs — API docs, if you want to poke at it directly

New Changes Push Command :
git add .
git commit -m "Describe what changes you made here"
git push

## 19. Demo data

`backend/app/seed/seed_data.py` populates all 8 configured West Bengal
cities and generates ~100 realistic (but clearly synthetic) demo problems
for Siliguri and Kolkata - varied types, severities, wards, dates,
statuses, and some deliberately clustered "hotspots" so DBSCAN and
recurrence analytics have something real to find. Every demo `Problem`
row has `is_demo=True` and the UI labels it accordingly. Run with
`--reset` to wipe and regenerate.

## 20. API overview

Full endpoint list: [`docs/api.md`](docs/api.md). Interactive docs are
also auto-generated by FastAPI at **http://localhost:8000/docs** once the
backend is running.

## 21. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Frontend shows "Can't reach the NeceCity backend" | Backend isn't running, or `VITE_API_BASE_URL` doesn't match where it's listening. |
| Inspect & Analyze says "ML model is not configured" | Expected until you train a model and place weights at `ml/weights/nececity_yolo.pt` (see section 12-17 above). Every other page still works. |
| `alembic upgrade head` fails to connect | Check `DATABASE_URL`/`POSTGRES_*` in `backend/.env` and that Postgres/PostGIS is actually running and reachable. |
| `CREATE EXTENSION postgis` permission error | Your Postgres role needs `CREATEDB`/superuser rights the first time; the official `postgis/postgis` Docker image handles this automatically. |
| Map tiles don't load | Needs outbound internet access to `tile.openstreetmap.org` (free, no key needed). |
| `pip install torch` is very large/slow | Expected - see `ml/requirements.txt` comment. A CPU-only PyTorch build is fine for this project's scale. |

## 22. Future enhancement

See [`docs/future-roadmap.md`](docs/future-roadmap.md) for the full list
(authentication/RBAC, more cities, active learning, segmentation, video
analysis, predictive risk modelling, department assignment, scheduled
reports, ...) and, more importantly, *why* the current codebase was
structured so these can be added without a rewrite.

---

## Known limitations of this minor version

- No authentication - anyone with network access to the app can act on
  data (documented, not hidden - see Security section of the original
  project brief and `docs/architecture.md`).
- The bundled ML dataset is synthetic placeholder data; a real trained
  model requires you to collect/annotate real images (`ml/data/README.md`).
- Ward boundary polygons are optional and mostly unpopulated in demo
  data; ward *filtering* still works via `problems.ward_id` regardless.
- Hotspot/trend analytics need a reasonable amount of data to produce
  meaningful output - very small/fresh cities will show sparse insights.

## License / academic use

Built as an MCA minor project. Adapt freely for coursework, portfolio, or
further development.





