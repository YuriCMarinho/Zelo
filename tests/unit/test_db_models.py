from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import (
    AuditEvent,
    Booking,
    CostRecord,
    MaintenanceTicket,
    Property,
    Provider,
    Quote,
)
from app.db.seed import run_seed
from app.schemas.common import ProviderCategory, ReportedByRole, TicketStatus, TicketUrgency


def test_property_and_booking_models(db_session: Session) -> None:
    prop = Property(
        id="prop-test-1",
        name="Casa de Praia",
        description="Linda casa à beira mar",
        address="Rua da Praia 10",
        city="Ubatuba",
        state="SP",
    )
    db_session.add(prop)
    db_session.commit()

    booking = Booking(
        id="book-test-1",
        property_id=prop.id,
        guest_name="João Silva",
        guest_contact="+55 11 98888-0000",
        start_date=date.today(),
        end_date=date.today() + timedelta(days=2),
        status="confirmed",
    )
    db_session.add(booking)
    db_session.commit()

    retrieved = db_session.query(Property).filter_by(id="prop-test-1").first()
    assert retrieved is not None
    assert len(retrieved.bookings) == 1
    assert retrieved.bookings[0].guest_name == "João Silva"


def test_ticket_and_quote_relationships(db_session: Session) -> None:
    prop = Property(
        id="prop-test-2",
        name="Flat Jardins",
        description="Studio aconchegante",
        address="Alameda Santos 200",
        city="São Paulo",
        state="SP",
    )
    prov = Provider(
        id="prov-test-1",
        name="Eletricista Express",
        category=ProviderCategory.ELECTRICIAN.value,
        region="São Paulo",
        phone="+55 11 91111-2222",
        is_validated=True,
    )
    db_session.add_all([prop, prov])
    db_session.commit()

    ticket = MaintenanceTicket(
        id="tick-test-1",
        run_id="run-test-abc",
        property_id=prop.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.ELECTRICIAN.value,
        urgency=TicketUrgency.URGENT.value,
        location_in_property="Quarto",
        description="Tomada pegando fogo",
        status=TicketStatus.REQUESTING_QUOTES.value,
        selected_provider_id=prov.id,
        notify_tenant=True,
    )
    db_session.add(ticket)
    db_session.commit()

    quote = Quote(
        id="quote-test-1",
        ticket_id=ticket.id,
        run_id="run-test-abc",
        provider_id=prov.id,
        amount=180.0,
        description="Troca de disjuntor e fiação",
        proposed_availability="Hoje às 17h",
        status="received",
    )
    db_session.add(quote)
    db_session.commit()

    retrieved_ticket = db_session.query(MaintenanceTicket).filter_by(id="tick-test-1").first()
    assert retrieved_ticket is not None
    assert len(retrieved_ticket.quotes) == 1
    assert retrieved_ticket.quotes[0].amount == 180.0
    assert retrieved_ticket.selected_provider is not None
    assert retrieved_ticket.selected_provider.name == "Eletricista Express"


def test_audit_and_cost_records(db_session: Session) -> None:
    audit = AuditEvent(
        id="aud-1",
        run_id="run-test-aud",
        node="router",
        event_type="message_received",
        payload={"message": "olá"},
    )
    cost = CostRecord(
        id="cost-1",
        run_id="run-test-aud",
        node="router",
        model="Qwen/Qwen3.5-4B",
        input_tokens=200,
        output_tokens=30,
        cost_usd=0.000026,
        is_mock=True,
    )
    db_session.add_all([audit, cost])
    db_session.commit()

    assert db_session.query(AuditEvent).count() == 1
    assert db_session.query(CostRecord).count() == 1


def test_run_seed_idempotency(db_session: Session) -> None:
    # Primeira execução do seed
    counts_1 = run_seed(db_session)
    assert counts_1["properties"] == 3
    assert counts_1["providers"] >= 5
    assert counts_1["tickets"] >= 1
    assert counts_1["bookings"] >= 3

    # Segunda execução deve manter os dados sem duplicar
    counts_2 = run_seed(db_session)
    assert counts_2["properties"] == 3
    assert counts_2["providers"] == counts_1["providers"]
    assert counts_2["tickets"] == counts_1["tickets"]


def test_api_health_endpoints(client: TestClient, db_session: Session) -> None:
    # Teste GET /health
    resp = client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "healthy"
    assert data["app"] == "SmartRepair AI"

    # Teste GET /health/db
    resp_db = client.get("/health/db")
    assert resp_db.status_code == 200
    db_data = resp_db.json()
    assert db_data["database"] == "connected"

    # Teste GET /api/properties e GET /api/tickets com seed
    run_seed(db_session)
    resp_props = client.get("/api/properties")
    assert resp_props.status_code == 200
    props = resp_props.json()
    assert len(props) == 3

    resp_tickets = client.get("/api/tickets")
    assert resp_tickets.status_code == 200
    tickets = resp_tickets.json()
    assert len(tickets) >= 1
    assert tickets[0]["run_id"] == "run-demo-seed-001"
