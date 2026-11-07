from datetime import datetime
from typing import Any

from pydantic import Field

from app.schemas.common import BaseSchema


class AuditEventCreate(BaseSchema):
    run_id: str = Field(..., min_length=1)
    ticket_id: str | None = None
    node: str = Field(
        ...,
        description="router, commercial_node1, validator_node2, scraper_nodeS, resolver_node3, adm",
    )
    event_type: str = Field(
        ...,
        description=(
            "message_received, ticket_created, quote_requested, quote_received, "
            "adm_approval, date_scheduled, tenant_notified, guardrail_blocked"
        ),
    )
    payload: dict[str, Any] = Field(default_factory=dict)


class AuditEventRead(AuditEventCreate):
    id: str
    created_at: datetime
