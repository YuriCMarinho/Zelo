from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import (
    BaseSchema,
    ProviderCategory,
    ReportedByRole,
    TicketStatus,
    TicketUrgency,
)


class TicketBase(BaseSchema):
    run_id: str = Field(
        ...,
        min_length=1,
        description="UUID ou identificador da execução ponta a ponta",
    )
    property_id: str = Field(..., min_length=1)
    reported_by_role: ReportedByRole = Field(default=ReportedByRole.TENANT)
    category: ProviderCategory
    urgency: TicketUrgency
    location_in_property: str = Field(..., min_length=2, max_length=150)
    description: str = Field(..., min_length=5)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("run_id não pode ser vazio")
        return v.strip()


class TicketCreateRequest(TicketBase):
    pass


class TicketUpdateRequest(BaseSchema):
    status: TicketStatus | None = None
    selected_provider_id: str | None = None
    scheduled_date: datetime | None = None
    notify_tenant: bool | None = None


class TicketApprovalRequest(BaseSchema):
    run_id: str | None = Field(
        default=None,
        description=(
            "UUID ou identificador da execução ponta a ponta. Se omitido, usa o run_id do ticket."
        ),
    )
    provider_id: str = Field(..., min_length=1)


class MaintenanceTicketRead(TicketBase):
    id: str
    status: TicketStatus
    selected_provider_id: str | None = None
    scheduled_date: datetime | None = None
    notify_tenant: bool = False
    created_at: datetime
    updated_at: datetime
