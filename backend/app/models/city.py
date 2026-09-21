from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class City(Base):
    """
    A monitored city/municipality.

    NeceCity is not hard-coded to a single city: every city (Siliguri,
    Kolkata, Asansol, ...) is a row here, configured through data rather
    than through source code, so a new city can be added without touching
    application logic (see project rule 26 - city architecture).
    """
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False, index=True)
    state: Mapped[str] = mapped_column(String(120), nullable=False, default="West Bengal")

    # Used to initially center the Leaflet map for this city.
    center_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    center_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    default_zoom: Mapped[int] = mapped_column(default=13)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    wards: Mapped[list["Ward"]] = relationship(back_populates="city", cascade="all, delete-orphan")
    locations: Mapped[list["Location"]] = relationship(back_populates="city", cascade="all, delete-orphan")
    problems: Mapped[list["Problem"]] = relationship(back_populates="city", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<City {self.slug}>"
