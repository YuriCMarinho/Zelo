import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.db.models.property import Property
    from app.db.models.provider import Provider
    from app.db.models.quote import Quote


class MaintenanceTicket(Base):
    __tablename__ = "maintenance_tickets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    property_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("properties.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reported_by_role: Mapped[str] = mapped_column(String(30), default="tenant", nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    urgency: Mapped[str] = mapped_column(String(20), default="normal", nullable=False, index=True)
    location_in_property: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="triaging", nullable=False, index=True)
    selected_provider_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("providers.id", ondelete="SET NULL"), nullable=True
    )
    scheduled_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notify_tenant: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    adm_synthesis: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    property: Mapped["Property"] = relationship("Property", back_populates="tickets")
    selected_provider: Mapped["Provider | None"] = relationship(
        "Provider", back_populates="selected_tickets"
    )
    quotes: Mapped[list["Quote"]] = relationship(
        "Quote", back_populates="ticket", cascade="all, delete-orphan"
    )
