from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import RoadImportance


class Location(Base):
    """
    A specific geographic point where one or more problems have been
    observed. `geom` is a PostGIS POINT used for spatial queries (distance,
    clustering, ward containment); `latitude`/`longitude` are kept as plain
    floats alongside it purely for cheap reads on the frontend map without
    needing a spatial function call for every marker.
    """
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id", ondelete="CASCADE"), index=True)
    ward_id: Mapped[int | None] = mapped_column(ForeignKey("wards.id", ondelete="SET NULL"), nullable=True, index=True)

    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    geom = mapped_column(Geometry(geometry_type="POINT", srid=4326), nullable=False)

    address_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    road_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    road_importance: Mapped[RoadImportance] = mapped_column(
        Enum(RoadImportance, name="road_importance"), default=RoadImportance.LOCAL
    )

    # Simple boolean + label rather than a full infrastructure table -
    # sufficient for the minor version's risk engine, and easy to extend
    # into a proper `infrastructure` table in a future version.
    near_important_infrastructure: Mapped[bool] = mapped_column(default=False)
    infrastructure_note: Mapped[str | None] = mapped_column(String(150), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    city: Mapped["City"] = relationship(back_populates="locations")
    ward: Mapped["Ward | None"] = relationship(back_populates="locations")
    images: Mapped[list["Image"]] = relationship(back_populates="location")
    problems: Mapped[list["Problem"]] = relationship(back_populates="location")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Location ({self.latitude:.5f}, {self.longitude:.5f})>"
