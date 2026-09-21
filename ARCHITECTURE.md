# NeceCity — System Architecture & Data Flow

This document is the single reference for **how NeceCity is built, why it
was built that way, and exactly where every piece of data on screen
actually comes from**. It's written so you can explain the project
end-to-end without having to re-derive anything from the code.

---

## 1. System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│  BROWSER                                                             │
│  React 18 + React Router + Tailwind CSS                              │
│  ├─ CityContext        (which city is selected — shared everywhere)  │
│  ├─ useApi hook        (loading/error/data for every page)           │
│  ├─ services/api.js    (the ONLY file that talks to the backend)     │
│  └─ 6 pages: Command Center, City Monitor, Inspect & Analyze,        │
│              Insights, Action Center, AI Recommendations             │
└───────────────────────────┬───────────────────────────────────────────┘
                            │  REST / JSON (+ multipart file upload)
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  BACKEND — FastAPI (Python)                                          │
│  ├─ api/routes/    thin HTTP handlers only, no business logic        │
│  ├─ services/      orchestration (detection→problem, city summaries) │
│  ├─ analytics/     Data Science: pandas trends, scikit-learn DBSCAN  │
│  ├─ risk/          explainable weighted risk-scoring engine          │
│  ├─ ml/            YOLO inference wrapper (graceful degradation)     │
│  └─ models/schemas/ SQLAlchemy ORM + Pydantic contracts              │
└───────────────────────────┬───────────────────────────────────────────┘
                            │  SQLAlchemy + GeoAlchemy2
                            ▼
┌─────────────────────────────────────────────────────────────────────┐
│  PostgreSQL 16 + PostGIS 3                                           │
│  cities · wards · locations(geom) · images · detections · problems · │
│  risk_scores · resolutions                                           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  ml/  — separable training pipeline (not part of the running app)    │
│  data/ (classes, dataset, validator) → training/ → evaluation/ →     │
│  weights/nececity_yolo.pt  ← the backend loads THIS file at runtime  │
└─────────────────────────────────────────────────────────────────────┘
```

**Why this shape:** a modular monolith, not microservices — one backend
process, one database, one frontend build. Each backend concern
(routing, business logic, analytics, risk, ML) lives in its own folder
so any one of them can be read, tested, or replaced independently. See
`docs/architecture.md` for the deeper extensibility rationale.

## 2. Tech stack — what and why

| Layer | Technology | Why this, specifically |
|---|---|---|
| ML / CV | PyTorch, Ultralytics YOLOv8n, OpenCV | YOLOv8n trains fast (even CPU/Colab-GPU) and loads quickly inside a web backend — important for a project that must be demoable, not just accurate |
| Data Science | Pandas, scikit-learn, GeoPandas | Pandas for time-series resampling (Insights trends), scikit-learn's DBSCAN for hotspot clustering, GeoPandas/Shapely for spatial data prep |
| Backend | FastAPI | Async-capable, auto-generates OpenAPI docs (`/docs`), first-class Pydantic validation |
| Database | PostgreSQL + PostGIS | Real spatial queries (`ST_DWithin`) for risk density and duplicate-detection — a naive lat/lng distance formula is measurably wrong at city scale |
| Frontend | React + Vite + Tailwind | Component reuse across 6 data-heavy pages; Tailwind gives a consistent design-token system (see §3) without a heavier UI framework |
| Map | Leaflet + OpenStreetMap | Free, no API key, no usage cap — the project's "no paid dependency" requirement |
| Charts | Recharts | Composable, styleable to match the design system exactly |
| Reporting | ReportLab | Server-rendered PDF, no headless-browser dependency |
| Containerization | Docker Compose | One command (`docker compose up --build`) reproduces the whole stack |

## 3. Design system ("Civic SaaS")

Card-based layout on a soft neutral canvas, generous whitespace, pill
filters/badges, and a navy + orange accent palette sampled directly from
the NeceCity logo:

- **Canvas** `#F6F7FB`, **cards** white with `shadow-card` + `rounded-lg`
- **Navy** `#031D46` (headers, primary actions, active nav) / **Orange**
  `#FD6001` (accents, CTAs, highlights)
- **Pills** (`rounded-full`) for every filter chip and status/severity badge
- One typeface throughout: Public Sans

All tokens live in `frontend/tailwind.config.js`; component-level classes
(`.panel`, `.btn-*`, `.pill*`) live in `frontend/src/styles/index.css` so
the whole app restyles from two files, not scattered inline styles.

> **Note on the sidebar logo:** an earlier version placed the logo on a
> solid dark-navy sidebar. The logo's building mark is the *exact same*
> navy (`#031D46`) as that background, so it was rendering — just
> invisible. Fixed by moving to a light sidebar (`frontend/src/components/Sidebar.jsx`),
> where both the navy mark and the orange pin are visible against white.

## 4. Core problems and the solutions implemented

| # | Problem | Solution | Where |
|---|---|---|---|
| 1 | Municipalities learn about infrastructure problems reactively, with no way to compare severity across locations | End-to-end pipeline: detect → verify → risk-score → prioritize → act → track | Whole app; see §5 |
| 2 | An ML model can be wrong, and a minor project may not have a trained model yet | Every detection is confidence-scored and requires human Confirm/Reject before becoming a Problem; if no model is configured, the app **degrades gracefully** instead of crashing | `backend/app/ml/inference.py` (`NeceCityDetector`) |
| 3 | *(Fixed this round)* Inspect & Analyze dead-ended with no way to proceed when no model was trained | Added a **manual-entry fallback**: log a problem directly (type + severity you choose) any time, whether or not ML is available | `backend/app/services/detection_service.py` (`place_or_update_problem`), `POST /problems/manual`, `frontend/src/components/ManualEntryForm.jsx` |
| 4 | Naive lat/lng distance math is wrong for real-world proximity (degrees aren't uniform metres) | PostGIS `ST_DWithin` on a `geography` cast for both the risk engine's density factor and duplicate/recurrence detection | `backend/app/risk/engine.py`, `backend/app/services/problem_service.py` |
| 5 | The same real-world problem gets reported more than once | Confirming a detection near an existing unresolved Problem of the same type (within 30m) increments `recurrence_count` instead of creating a duplicate row | `place_or_update_problem` |
| 6 | Which locations should get attention first, and *why*? | A deterministic, weighted risk formula (severity, recurrence, density, road importance, infrastructure proximity) — never a random or hidden number, and every contributing factor is shown to the user | `backend/app/risk/engine.py` + `RiskScore.reasons`/`.components` |
| 7 | Spotting geographic clusters of problems, not just individual points | DBSCAN (density-based clustering) over problem coordinates — no need to pre-choose a cluster count, and it correctly ignores isolated points as noise | `backend/app/analytics/hotspots.py` |
| 8 | Citizens don't know who to actually contact to help resolve civic issues | A new **AI Recommendations** page combining real problem-data-driven insights with a curated directory of verified, real civic organizations | §6 below |
| 9 | A minor project can't be tied to one city | Every city is a database row, not a code constant — architecture supports any number of cities without touching source | `backend/app/models/city.py`, `backend/app/seed/seed_data.py` |
| 10 | *(Fixed this round)* A model trained only on synthetic placeholder data loads fine and silently returns "nothing detected" on real photos, looking like a bug | Training now writes a provenance sidecar file; the backend reads it and surfaces an honest warning in Inspect & Analyze and the top-bar status badge, rather than pretending accuracy that isn't there | `ml/training/train.py`, `backend/app/ml/inference.py` |
| 11 | *(Fixed this round)* Static "AI Recommendations" page felt like decoration, not real AI | Replaced with an actual chat interface: LLM-backed when a key is configured, and a genuinely useful data-grounded rule-based assistant when it isn't — never a dead end either way | `backend/app/services/chat_service.py`, `frontend/src/components/ChatPanel.jsx` |
| 12 | *(Fixed this round)* Logo appeared to be missing; native `<select>` city switcher couldn't be styled when open; favicon rendered stretched | Logo: moved off a background matching its own color. City switcher: replaced with a custom-built dropdown. Favicon: regenerated as a proper square icon from the (non-square) source pin artwork | `frontend/src/components/Sidebar.jsx`, `CitySelector.jsx`, `frontend/index.html` |

## 5. Data flow — exactly where every number on screen comes from

This is the map to use when you need to answer "where does *this*
number/label/image come from?" during a walkthrough or viva.

| Screen element | Source | How it gets there | Why this source |
|---|---|---|---|
| City list / selector | **Database** (`cities` table) | `GET /cities` → `CityContext` (React Context, cached client-side, selection persisted to `localStorage`) | Cities are data, not hardcoded — a new city is a DB insert, never a code change |
| Command Center stats (totals, severity/status/type breakdown, health score) | **Database**, aggregated live | `GET /cities/{id}/summary` runs real SQL `GROUP BY`/`COUNT` queries at request time — nothing is pre-computed or cached | Numbers must always reflect the current DB state, including problems added seconds ago |
| City Monitor map markers | **Database** | `GET /map/problems` — a live, filtered SQL query (multi-select type/severity/status, ward, date range) | Same single source of truth as every other page — no separate "map data" store |
| Inspect & Analyze detections (bounding boxes, class, confidence) | **ML model output**, or **absent** | `POST /analyze/image` runs local YOLO inference (`backend/app/ml/inference.py`) if `ml/weights/nececity_yolo.pt` exists; otherwise returns `model_available: false` — this is real model output or an honest "not available", never fabricated | The project's "no fake AI" rule: confidence values must be real model output, never invented |
| Inspect & Analyze suggested severity | **Deterministic heuristic**, not ML | `backend/app/ml/postprocessing.py` — a documented formula (class weight + relative box area), always editable by the human reviewer before it's saved | Explicitly *not* a second ML model — kept separate from model confidence per the project's evaluation-vs-prediction distinction |
| A confirmed/manual Problem's risk score | **Server-computed**, live | `app/risk/engine.py` runs at confirm-time and on every status change, querying the DB for real neighbour counts via PostGIS | Must reflect the current state of nearby problems, not a stale snapshot |
| Insights charts (by type/severity/area) | **Database**, aggregated live | `GET /analytics/overview` — real SQL grouping, no sampling | Same reasoning as Command Center |
| Insights trend line | **Database** + **Pandas** | `GET /analytics/trends` pulls raw timestamps from the DB, then Pandas `resample()` buckets them by week/month | A real time-series computation, not mocked data points |
| Insights hotspot clusters | **Database** + **scikit-learn** | `GET /analytics/hotspots` pulls problem coordinates, runs `DBSCAN` (haversine metric) | Genuine unsupervised clustering on real coordinates |
| Insights "Data Insight" sentences | **Database**, rule-based | `app/analytics/overview.py`/`trends.py`/`hotspots.py` — plain Python comparisons against the same aggregated numbers already shown in the charts | Deterministic, not an LLM — every sentence is traceable to a specific number |
| Action Center priority queue | **Database** | `GET /risk/priorities` — Problems ordered by their stored `RiskScore.score` | — |
| Action Center PDF/CSV report | **Database**, rendered server-side | `POST /reports` (ReportLab for PDF, Python `csv` module for CSV) queries the same Problem/RiskScore tables | The report is a formatted view of real data, generated on demand, not a static template |
| **AI Recommendations — city insights** | **Database**, rule-based | `app/services/recommendation_service.py get_city_recommendations()` reuses `get_city_summary()` (the *same* function Command Center uses) to find the top problem type, critical count, and health score, then generates sentences from those real numbers | Not fabricated — literally the same aggregation function as Command Center, just narrated |
| **AI Recommendations — organizations directory** | **Static curated data**, verified real | A hardcoded Python list in `recommendation_service.py`: real, independently verifiable organizations (SaveLIFE Foundation, Sulabh International, Janaagraha, the government's own Swachhata/Swachh Bharat Mission platform, etc.), each linking to its real official website | These are **not** user data, **not** ML output, and **not invented contact details** — see the sourcing note in §6 |
| **AI Recommendations — civic tips** | **Static curated content** | Same file, `CIVIC_TIPS` — generic, non-fabricated actionable guidance, not tied to any one city's data | Baseline advice that's true regardless of what a specific city's analytics currently show |
| **AI Recommendations — chat replies** | **LLM API** (if `LLM_API_KEY` configured) or **rule-based** (default) | `POST /chat` → `app/services/chat_service.py`. In LLM mode, the model is grounded with a system prompt built from the same real city summary + organization directory (never left to invent its own facts). In rule-based mode (the default, no external calls), keyword-intent matching answers directly from the database. Every reply is labeled with which mode produced it, in the UI. | Chat works fully out of the box with zero external dependencies, and gets strictly better (more open-ended) if you bring your own API key — the same graceful-degradation pattern as the YOLO model |
| Model status badge (top bar, every page) | **Live from the ML service** | `GET /ml/status` reads the same `NeceCityDetector` singleton Inspect & Analyze uses | Makes the ML integration visible everywhere, not just on the one page that uses it directly |
| Demo/seed data (the ~100 sample problems) | **Generated once**, clearly labeled | `backend/app/seed/seed_data.py`, run manually (`python -m app.seed.seed_data`) — every row it creates has `is_demo=True` and the UI shows a banner when a city's data includes it | Needed so a fresh install has something to demo; never presented as real municipal records |

### Frontend state — what's client-only vs. server-sourced

| State | Where it lives | Persisted? |
|---|---|---|
| Selected city | `CityContext` (React Context) | Yes — `localStorage`, so it survives a page refresh |
| Any page's data (stats, map markers, analytics, etc.) | Component state via the `useApi` hook | No — re-fetched from the backend every time the page/city changes; never stale-cached |
| Inspect & Analyze's in-progress review (uploaded file preview, per-detection Confirm/Reject/severity edits before submission) | Local `useState` in `InspectAnalyze.jsx` | No — intentionally ephemeral; only becomes persistent data once you click Confirm/Log, at which point it's written to the database via the API |
| Manual-entry form fields | Local `useState` in `InspectAnalyze.jsx` | No, same as above |

There is **no global state library** (Redux/Zustand/etc.) in this
project — React Context (for the one genuinely cross-page value, the
selected city) plus a small shared data-fetching hook (`useApi`) is
sufficient for six pages of this shape, and avoids the "unnecessary
complexity" the project's own build brief explicitly warns against.

## 6. Sourcing note: the AI Recommendations organization directory

Every organization listed under **AI Recommendations** was found via web
search and cross-checked against its own official site or Wikipedia
entry before being added — no name, description, or URL in that list was
invented. Deliberately **excluded**: any specific local branch address or
phone number for a named organization, because getting that detail wrong
for a real organization would actively mislead someone trying to contact
them. Instead, the directory links to each organization's own official
website, and the page tells the user to verify current contact details
there and to check with their municipal corporation for anything
hyperlocal. If you deploy this for a real city, replace/extend this list
with your municipality's actual verified local contacts.

## 7. Where to go next

- Everyday setup/run commands → `README.md`
- Deeper extensibility rationale (why DBSCAN, why PostGIS, what future
  features touch vs. don't) → `docs/architecture.md`
- Database schema → `docs/database.md`
- ML pipeline / training → `docs/ml-pipeline.md`, `ml/data/README.md`
- API endpoint reference → `docs/api.md`
