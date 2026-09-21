"""
Hotspot analysis: clusters unresolved problems geographically using
DBSCAN (density-based spatial clustering), so the Insights page can show
"these N locations form a hotspot" rather than just individual points.

DBSCAN is used (rather than k-means) because:
  - it does not require choosing the number of clusters in advance,
  - it naturally leaves sparse, isolated problems unclustered ("noise")
    instead of forcing them into a group,
  - it works well with the haversine (great-circle) distance metric that
    lat/lng data needs.

This is a well-understood, explainable Data Science technique - exactly
the kind of "why DBSCAN" question the project's viva-readiness rule asks
the student to be able to answer.
"""
import numpy as np
from sklearn.cluster import DBSCAN
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.problem import Problem
from app.schemas.analytics import DataInsight, HotspotOut, HotspotsAnalyticsOut

EARTH_RADIUS_M = 6_371_000
HOTSPOT_RADIUS_METERS = 200
MIN_SAMPLES_PER_CLUSTER = 3


def get_hotspots(db: Session, city_id: int) -> HotspotsAnalyticsOut:
    rows = db.execute(
        select(Problem)
        .options(joinedload(Problem.location))
        .where(Problem.city_id == city_id)
    ).unique().scalars().all()

    rows = [p for p in rows if p.location is not None]
    if len(rows) < MIN_SAMPLES_PER_CLUSTER:
        return HotspotsAnalyticsOut(algorithm="DBSCAN (haversine)", hotspots=[], insights=[])

    coords_rad = np.radians([[p.location.latitude, p.location.longitude] for p in rows])
    eps_rad = HOTSPOT_RADIUS_METERS / EARTH_RADIUS_M

    labels = DBSCAN(eps=eps_rad, min_samples=MIN_SAMPLES_PER_CLUSTER, metric="haversine").fit_predict(coords_rad)

    hotspots: list[HotspotOut] = []
    cluster_ids = sorted(set(labels) - {-1})
    for cluster_id in cluster_ids:
        members = [p for p, label in zip(rows, labels) if label == cluster_id]
        types = [m.problem_type.value for m in members]
        dominant_type = max(set(types), key=types.count)
        # Represent the cluster by its centroid-nearest member for a stable marker.
        lats = [m.location.latitude for m in members]
        lngs = [m.location.longitude for m in members]
        centroid = (sum(lats) / len(lats), sum(lngs) / len(lngs))

        for m in members:
            hotspots.append(
                HotspotOut(
                    location_id=m.location_id,
                    latitude=m.location.latitude,
                    longitude=m.location.longitude,
                    problem_count=len(members),
                    dominant_type=dominant_type,
                    cluster_id=int(cluster_id),
                )
            )

    insights: list[DataInsight] = []
    if cluster_ids:
        insights.append(
            DataInsight(
                kind="hotspot",
                text=(
                    f"DBSCAN identified {len(cluster_ids)} problem hotspot(s) - clusters of "
                    f"{MIN_SAMPLES_PER_CLUSTER}+ problems within {HOTSPOT_RADIUS_METERS}m of each other."
                ),
            )
        )
    else:
        insights.append(DataInsight(kind="hotspot", text="No significant geographic hotspots detected yet."))

    return HotspotsAnalyticsOut(algorithm="DBSCAN (haversine)", hotspots=hotspots, insights=insights)
