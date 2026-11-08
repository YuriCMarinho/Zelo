import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.quote import Quote
    from app.db.models.ticket import MaintenanceTicket


class Provider(Base):
    __tablename__ = "providers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    region: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    is_validated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    rating: Mapped[float | None] = mapped_column(Float, default=4.8, nullable=True)
    reviews_count: Mapped[int] = mapped_column(Integer, default=42, nullable=False)
    address: Mapped[str | None] = mapped_column(String(220), nullable=True)
    source: Mapped[str] = mapped_column(String(50), default="web_maps", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )

    quotes: Mapped[list["Quote"]] = relationship("Quote", back_populates="provider")
    selected_tickets: Mapped[list["MaintenanceTicket"]] = relationship(
        "MaintenanceTicket", back_populates="selected_provider"
    )
