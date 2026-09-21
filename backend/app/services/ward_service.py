from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.ward import Ward


def list_wards(db: Session, city_id: int) -> list[Ward]:
    stmt = select(Ward).where(Ward.city_id == city_id).order_by(Ward.name)
    return list(db.execute(stmt).scalars().all())
