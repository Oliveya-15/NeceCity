# NeceCity backend image.
#
# Includes the full ML stack (torch/ultralytics/opencv) since inference
# runs in-process inside the FastAPI app (see app/ml/inference.py) - this
# makes the image large (a few GB), which is expected for a self-hosted
# CV model and is the tradeoff documented in docs/setup.md in exchange for
# never depending on an external inference API.
FROM python:3.11-slim

# System libraries required by psycopg2 (libpq) and OpenCV (libGL/glib).
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc libgl1 libglib2.0-0 curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/uploads

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD curl -f http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
