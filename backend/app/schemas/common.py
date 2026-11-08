import re
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# Texto obrigatório: remove espaços nas pontas e rejeita vazio (ex.: run_id, ids).
NonBlankStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


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


_S = TicketStatus

# Transições permitidas (docs/PLAN.md §3). Quem muda o status do ticket deve
# consultar is_valid_ticket_transition; aprovação do ADM não pode ser pulada.
TICKET_TRANSITIONS: dict[TicketStatus, frozenset[TicketStatus]] = {
    _S.TRIAGING: frozenset({_S.TRIAGING, _S.OPEN}),
    _S.OPEN: frozenset({_S.NO_PROVIDERS_FALLBACK, _S.REQUESTING_QUOTES}),
    _S.NO_PROVIDERS_FALLBACK: frozenset({_S.REQUESTING_QUOTES, _S.ESCALATED_TO_ADM}),
    _S.REQUESTING_QUOTES: frozenset({_S.WAITING_QUOTES}),
    _S.WAITING_QUOTES: frozenset({_S.AWAITING_ADM_APPROVAL, _S.ESCALATED_TO_ADM}),
    _S.AWAITING_ADM_APPROVAL: frozenset({_S.AWAITING_ADM_APPROVAL, _S.PROPOSING_DATE}),
    _S.PROPOSING_DATE: frozenset({_S.WAITING_DATE_CONFIRMATION}),
    _S.WAITING_DATE_CONFIRMATION: frozenset(
        {_S.PROPOSING_DATE, _S.ESCALATED_TO_ADM, _S.CONFIRMED_SCHEDULE}
    ),
    _S.CONFIRMED_SCHEDULE: frozenset({_S.NOTIFYING_TENANT, _S.RESOLVED}),
    _S.NOTIFYING_TENANT: frozenset({_S.RESOLVED}),
    _S.RESOLVED: frozenset(),
    _S.ESCALATED_TO_ADM: frozenset(),
}


def is_valid_ticket_transition(current: TicketStatus, new: TicketStatus) -> bool:
    """Indica se o ticket pode passar de `current` para `new`."""
    return new in TICKET_TRANSITIONS[current]


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
