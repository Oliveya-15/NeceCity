from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.enums import ImageSource


class Image(Base):
    """
    A street-level image, either uploaded by a user through Inspect &
    Analyze or bundled as demo/seed data. Stores only a path + metadata;
    the binary file lives on disk under `UPLOAD_DIR` (never in the
    database), which keeps the DB small and backups simple.
    """
    __tablename__ = "images"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id", ondelete="SET NULL"), nullable=True)

    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)

    source: Mapped[ImageSource] = mapped_column(Enum(ImageSource, name="image_source"), default=ImageSource.UPLOAD)

    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    location: Mapped["Location | None"] = relationship(back_populates="images")
    detections: Mapped[list["Detection"]] = relationship(back_populates="image", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Image {self.original_filename or self.file_path}>"
