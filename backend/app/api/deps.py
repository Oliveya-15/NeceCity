from fastapi import Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.city import City
from app.services.city_service import get_city


def get_city_or_404(city_id: int, db: Session = Depends(get_db)) -> City:
    city = get_city(db, city_id)
    if city is None:
        raise HTTPException(status_code=404, detail=f"City {city_id} not found.")
    return city


class PageParams:
    def __init__(
        self,
        page: int = Query(default=1, ge=1),
        page_size: int | None = Query(default=None, ge=1, alias="page_size"),
    ):
        settings = get_settings()
        self.page = page
        self.page_size = min(page_size or settings.DEFAULT_PAGE_SIZE, settings.MAX_PAGE_SIZE)
