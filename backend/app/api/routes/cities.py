from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_city_or_404
from app.db.session import get_db
from app.models.city import City
from app.schemas.city import CityOut, CitySummaryOut
from app.services import city_service, ward_service

router = APIRouter(prefix="/cities", tags=["cities"])


@router.get("", response_model=list[CityOut])
def list_cities(db: Session = Depends(get_db)):
    return city_service.list_cities(db)


@router.get("/{city_id}/summary", response_model=CitySummaryOut)
def city_summary(city: City = Depends(get_city_or_404), db: Session = Depends(get_db)):
    return city_service.get_city_summary(db, city)


@router.get("/{city_id}/wards")
def city_wards(city: City = Depends(get_city_or_404), db: Session = Depends(get_db)):
    wards = ward_service.list_wards(db, city.id)
    return [{"id": w.id, "name": w.name, "code": w.code} for w in wards]
