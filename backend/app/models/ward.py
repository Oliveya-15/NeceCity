from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Ward(Base):
    """
    An administrative sub-division of a city (ward / area / zone).

    `boundary` is an optional PostGIS polygon. It is nullable because the
    minor-version demo data may only have a handful of wards digitised; the
    application must still work using `problems.ward_id` for filtering even
    when no polygon geometry is available for a given ward.
    """
    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str | None] = mapped_column(String(30), nullable=True)

    boundary = mapped_column(Geometry(geometry_type="POLYGON", srid=4326), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    city: Mapped["City"] = relationship(back_populates="wards")
    locations: Mapped[list["Location"]] = relationship(back_populates="ward")
    problems: Mapped[list["Problem"]] = relationship(back_populates="ward")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Ward {self.name} (city={self.city_id})>"
