import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict


class ProviderCategory(StrEnum):
    PLUMBER = "plumber"
    ELECTRICIAN = "electrician"
    PAINTER = "painter"
    ORGANIZER = "organizer"
    GENERAL_MAINTENANCE = "general_maintenance"


class TicketUrgency(StrEnum):
    URGENT = "urgent"
    NORMAL = "normal"


class TicketStatus(StrEnum):
    """Estados do ticket do Fluxo C; espelha a máquina de estados de docs/PLAN.md §3."""

    TRIAGING = "triaging"
    OPEN = "open"
    NO_PROVIDERS_FALLBACK = "no_providers_fallback"
    REQUESTING_QUOTES = "requesting_quotes"
    WAITING_QUOTES = "waiting_quotes"
    AWAITING_ADM_APPROVAL = "awaiting_adm_approval"
    PROPOSING_DATE = "proposing_date"
    WAITING_DATE_CONFIRMATION = "waiting_date_confirmation"
    CONFIRMED_SCHEDULE = "confirmed_schedule"
    NOTIFYING_TENANT = "notifying_tenant"
    RESOLVED = "resolved"
    ESCALATED_TO_ADM = "escalated_to_adm"


class ReportedByRole(StrEnum):
    TENANT = "tenant"
    CLEANER = "cleaner"
    HOST = "host"


class QuoteStatus(StrEnum):
    REQUESTED = "requested"
    RECEIVED = "received"
    REJECTED = "rejected"
    SELECTED = "selected"
    TIMEOUT = "timeout"


class RouteDestination(StrEnum):
    COMMERCIAL_NODE1 = "commercial_node1"
    MAINTENANCE_NODE2 = "maintenance_node2"


def mask_phone(phone: str | None) -> str:
    """Mascara número de telefone para conformidade com a LGPD."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 4:
        return "***"
    prefix = digits[:2]
    suffix = digits[-2:]
    masked_count = len(digits) - 4
    return f"({prefix}) {'*' * masked_count}-{suffix}"


class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)
