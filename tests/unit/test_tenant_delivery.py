from datetime import UTC, datetime, timedelta

import pytest

from app.agents.resolver_graph import notify_tenant_and_resolve
from app.db.models import AuditEvent, Booking, ChatMessageRecord, MaintenanceTicket, Property


@pytest.mark.asyncio
@pytest.mark.parametrize("has_occupant", [True, False])
async def test_notification_is_delivered_only_to_occupant_session(db_session, has_occupant):
    visit = datetime.now(UTC) + timedelta(days=1)
    prop = Property(name="Imóvel", description="Teste", address="Rua", city="Fortaleza", state="CE")
    db_session.add(prop)
    db_session.flush()
    if has_occupant:
        db_session.add(
            Booking(
                property_id=prop.id,
                guest_name="Hóspede",
                guest_contact="teste@example.invalid",
                session_id="occupant-session",
                start_date=visit.date() - timedelta(days=1),
                end_date=visit.date() + timedelta(days=1),
                status="confirmed",
            )
        )
    db_session.add(
        Booking(
            property_id=prop.id,
            guest_name="Futuro",
            guest_contact="teste@example.invalid",
            session_id="future-session",
            start_date=visit.date() + timedelta(days=10),
            end_date=visit.date() + timedelta(days=11),
            status="confirmed",
        )
    )
    ticket = MaintenanceTicket(
        property_id=prop.id,
        run_id="delivery-test",
        reported_by_role="tenant",
        description="Torneira vazando",
        category="plumber",
        urgency="urgent",
        location_in_property="Cozinha",
        status="confirmed_schedule",
        scheduled_date=visit,
    )
    db_session.add(ticket)
    db_session.commit()
    await notify_tenant_and_resolve(
        {
            "ticket_id": ticket.id,
            "property_id": prop.id,
            "run_id": ticket.run_id,
            "notify_tenant": True,
            "proposed_date": visit.isoformat(),
        }
    )
    messages = db_session.query(ChatMessageRecord).all()
    assert len(messages) == int(has_occupant)
    if has_occupant:
        assert messages[0].session_id == "occupant-session"
        assert messages[0].channel == "guest"
        assert messages[0].ticket_id == ticket.id
        assert messages[0].body
    count = db_session.query(AuditEvent).filter_by(event_type="tenant_notified").count()
    assert count == int(has_occupant)
