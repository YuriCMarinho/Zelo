import re
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.audit import AuditEventCreate
from app.schemas.booking import BookingCreate, BookingRead
from app.schemas.chat import ChatMessageInput, ChatMessageOutput
from app.schemas.common import (
    TICKET_TRANSITIONS,
    ProviderCategory,
    QuoteStatus,
    ReportedByRole,
    RouteDestination,
    TicketStatus,
    TicketUrgency,
    is_valid_ticket_transition,
    mask_phone,
)
from app.schemas.cost import CostRecordCreate, CostSummary
from app.schemas.property import PropertyCreate, PropertyRead
from app.schemas.provider import ProviderCreate, ProviderRead
from app.schemas.quote import QuoteCreateRequest, QuoteResponseCreate
from app.schemas.resolver import ResolutionRequest, ResolverStarter
from app.schemas.ticket import TicketApprovalRequest, TicketCreateRequest


def test_mask_phone_lgpd() -> None:
    assert mask_phone("+55 (11) 98765-4321") == "(55) *********-21"
    assert mask_phone("1234") == "(12) -34"
    assert mask_phone("12") == "***"
    assert mask_phone(None) == ""


def test_property_schemas() -> None:
    data = {
        "name": "Apartamento Copacabana",
        "description": "Belo apartamento com vista mar",
        "address": "Av Atlantica 100",
        "city": "Rio de Janeiro",
        "state": "RJ",
        "rules_faq": "Sem fumar",
    }
    prop_create = PropertyCreate(**data)
    assert prop_create.name == "Apartamento Copacabana"

    prop_read = PropertyRead(
        id="prop-1",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        **data,
    )
    assert prop_read.id == "prop-1"


def test_booking_schema_validations() -> None:
    today = date.today()
    booking = BookingCreate(
        property_id="prop-1",
        guest_name="Hóspede Teste",
        guest_contact="+55 21 99999-0000",
        start_date=today,
        end_date=today,
        status="confirmed",
    )
    assert booking.guest_name == "Hóspede Teste"

    read = BookingRead(
        id="b-1",
        property_id="prop-1",
        guest_name="Hóspede Teste",
        guest_contact="+55 (21) 99999-0000",
        start_date=today,
        end_date=today,
        status="confirmed",
        created_at=datetime.now(UTC),
    )
    assert read.masked_contact.startswith("(55)")

    # Data de término anterior à de início deve falhar
    with pytest.raises(ValidationError):
        BookingCreate(
            property_id="prop-1",
            guest_name="Hóspede Teste",
            guest_contact="+55 21 99999-0000",
            start_date=date(2026, 11, 10),
            end_date=date(2026, 11, 5),
            status="confirmed",
        )


def test_provider_schemas() -> None:
    provider = ProviderCreate(
        name="Mario Encanador",
        category=ProviderCategory.PLUMBER,
        region="Zona Sul",
        phone="+55 21 98888-7777",
        is_validated=True,
    )
    assert provider.category == ProviderCategory.PLUMBER

    read = ProviderRead(
        id="prov-1",
        name="Mario Encanador",
        category=ProviderCategory.PLUMBER,
        region="Zona Sul",
        phone="+55 21 98888-7777",
        is_validated=True,
        rating=4.9,
        source="google_places",
        created_at=datetime.now(UTC),
    )
    assert "*" in read.masked_phone


def test_ticket_schema_run_id_required() -> None:
    # run_id vazio deve falhar
    with pytest.raises(ValidationError):
        TicketCreateRequest(
            run_id="   ",
            property_id="prop-1",
            reported_by_role=ReportedByRole.TENANT,
            category=ProviderCategory.PLUMBER,
            urgency=TicketUrgency.URGENT,
            location_in_property="Cozinha",
            description="Vazamento sério",
        )

    # run_id válido deve passar
    ticket = TicketCreateRequest(
        run_id="run-test-123",
        property_id="prop-1",
        reported_by_role=ReportedByRole.CLEANER,
        category=ProviderCategory.ELECTRICIAN,
        urgency=TicketUrgency.NORMAL,
        location_in_property="Quarto principal",
        description="Lâmpada queimada e tomada solta",
    )
    assert ticket.run_id == "run-test-123"
    assert ticket.reported_by_role == ReportedByRole.CLEANER


def test_ticket_approval_request() -> None:
    req = TicketApprovalRequest(run_id="run-1", provider_id="prov-1")
    assert req.provider_id == "prov-1"


def test_quote_schemas() -> None:
    with pytest.raises(ValidationError):
        QuoteCreateRequest(
            ticket_id="tick-1",
            run_id="",
            provider_id="prov-1",
            amount=150.0,
        )

    quote = QuoteCreateRequest(
        ticket_id="tick-1",
        run_id="run-1",
        provider_id="prov-1",
        amount=150.0,
        description="Troca de reparo",
        status=QuoteStatus.REQUESTED,
    )
    assert quote.amount == 150.0

    resp = QuoteResponseCreate(run_id="run-1", amount=200.0, proposed_availability="Amanhã 14h")
    assert resp.amount == 200.0


def test_chat_schemas() -> None:
    chat_in = ChatMessageInput(
        property_id="prop-1",
        message="Gostaria de saber se tem secador de cabelo no quarto.",
        sender_role=ReportedByRole.TENANT,
    )
    assert chat_in.property_id == "prop-1"

    chat_out = ChatMessageOutput(
        run_id="run-chat-1",
        property_id="prop-1",
        route_destination=RouteDestination.COMMERCIAL_NODE1,
        response_text="Sim! Há secador de cabelo disponível em todos os banheiros.",
    )
    assert chat_out.route_destination == RouteDestination.COMMERCIAL_NODE1


def test_audit_and_cost_schemas() -> None:
    audit = AuditEventCreate(
        run_id="run-audit-1",
        ticket_id="ticket-1",
        node="router",
        event_type="message_received",
        payload={"raw": "ping"},
    )
    assert audit.node == "router"

    cost = CostRecordCreate(
        run_id="run-cost-1",
        node="validator_node2",
        model="Qwen/Qwen3.5-4B",
        input_tokens=100,
        output_tokens=30,
        cost_usd=0.000016,
        is_mock=True,
    )
    assert cost.is_mock is True

    summary = CostSummary(
        total_cost_usd=0.005,
        total_input_tokens=5000,
        total_output_tokens=1200,
        total_calls=12,
        by_node={"validator_node2": 0.002, "resolver_node3": 0.003},
        by_model={"Qwen/Qwen3.5-4B": 0.005},
        budget_limit_usd=25.00,
        percentage_used=0.02,
        alert_triggered=None,
    )
    assert summary.percentage_used == 0.02


def test_ticket_transitions_match_plan_state_machine() -> None:
    """TicketStatus e TICKET_TRANSITIONS devem bater com o diagrama de docs/PLAN.md §3."""
    plan = Path(__file__).resolve().parents[2] / "docs" / "PLAN.md"
    if not plan.exists():
        pytest.skip("docs/PLAN.md fora deste checkout (ex.: imagem só do backend)")
    diagram = plan.read_text(encoding="utf-8").split("stateDiagram-v2", 1)[1].split("```", 1)[0]
    pairs = re.findall(r"^\s*(\S+)\s*-->\s*([^:\s]+)", diagram, flags=re.MULTILINE)
    plan_edges = {(a, b) for a, b in pairs if "[*]" not in (a, b)}
    plan_states = {state for edge in plan_edges for state in edge}

    assert plan_states == {status.name for status in TicketStatus}
    code_edges = {(a.name, b.name) for a, targets in TICKET_TRANSITIONS.items() for b in targets}
    assert code_edges == plan_edges


def test_ticket_transitions_block_skipping_adm_approval() -> None:
    s = TicketStatus
    assert is_valid_ticket_transition(s.AWAITING_ADM_APPROVAL, s.PROPOSING_DATE)
    assert not is_valid_ticket_transition(s.TRIAGING, s.CONFIRMED_SCHEDULE)
    assert not is_valid_ticket_transition(s.WAITING_QUOTES, s.PROPOSING_DATE)
    assert not is_valid_ticket_transition(s.RESOLVED, s.OPEN)


def test_resolution_request_rejects_blank_ids() -> None:
    for blank in ("", "   "):
        with pytest.raises(ValidationError):
            ResolutionRequest(ticket_id="t-1", run_id=blank)
        with pytest.raises(ValidationError):
            ResolutionRequest(ticket_id=blank, run_id="r-1")
    assert ResolutionRequest(ticket_id=" t-1 ", run_id=" r-1 ").run_id == "r-1"


def test_resolver_starter_protocol_is_satisfied_statically() -> None:
    started: list[ResolutionRequest] = []

    class FakeResolver:
        def start_resolution(self, request: ResolutionRequest) -> None:
            started.append(request)

    # Contrato de uso. A garantia estática vem da S2-T6, que anota sua implementação
    # como ResolverStarter em app/ (coberto por `mypy app`).
    resolver: ResolverStarter = FakeResolver()
    resolver.start_resolution(ResolutionRequest(ticket_id="t-1", run_id="r-1"))
    assert started[0].run_id == "r-1"
