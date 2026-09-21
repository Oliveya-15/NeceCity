from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics import hotspots, overview, recurring, trends
from app.db.session import get_db
from app.schemas.analytics import (
    HotspotsAnalyticsOut,
    OverviewAnalyticsOut,
    RecurringProblemOut,
    TrendsAnalyticsOut,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=OverviewAnalyticsOut)
def get_overview(city_id: int, db: Session = Depends(get_db)):
    return overview.get_overview(db, city_id)


@router.get("/trends", response_model=TrendsAnalyticsOut)
def get_trends(city_id: int, granularity: str = "week", db: Session = Depends(get_db)):
    return trends.get_trends(db, city_id, granularity=granularity)


@router.get("/hotspots", response_model=HotspotsAnalyticsOut)
def get_hotspots(city_id: int, db: Session = Depends(get_db)):
    return hotspots.get_hotspots(db, city_id)


@router.get("/recurring", response_model=list[RecurringProblemOut])
def get_recurring(city_id: int, db: Session = Depends(get_db)):
    return recurring.get_recurring_problems(db, city_id)
