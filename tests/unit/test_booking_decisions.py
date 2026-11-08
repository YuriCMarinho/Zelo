from datetime import date, timedelta

import pytest

from app.db.models import AuditEvent, Booking, ChatMessageRecord, Property


@pytest.fixture
def booking(db_session):
    prop = Property(name="Imóvel", description="Teste", address="Rua", city="Fortaleza", state="CE")
    db_session.add(prop)
    db_session.flush()
    booking = Booking(
        property_id=prop.id,
        guest_name="Teste",
        guest_contact="teste@example.invalid",
        start_date=date.today() + timedelta(days=50),
        end_date=date.today() + timedelta(days=52),
        status="pending_approval",
        total_price=400,
        session_id="decisions",
    )
    db_session.add(booking)
    db_session.commit()
    return booking


def test_approval_retries_do_not_repeat_effects(client, db_session, booking):
    url = f"/api/bookings/{booking.id}/approve"
    assert client.post(url, json={"final_price": 400}).status_code == 200
    assert client.post(url, json={"final_price": 400}).status_code == 200
    assert db_session.query(ChatMessageRecord).filter_by(booking_id=booking.id).count() == 1
    assert db_session.query(AuditEvent).filter_by(event_type="booking_approved").count() == 1
    assert client.post(url, json={"final_price": 500}).status_code == 409
    assert (
        client.post(f"/api/bookings/{booking.id}/reject", json={"reason": "Sem vaga"}).status_code
        == 409
    )


def test_rejected_request_cannot_be_approved_again(client, db_session, booking):
    url = f"/api/bookings/{booking.id}/reject"
    assert client.post(url, json={"reason": "Sem vaga"}).status_code == 200
    assert client.post(url, json={"reason": "Sem vaga"}).status_code == 200
    assert db_session.query(ChatMessageRecord).filter_by(booking_id=booking.id).count() == 1
    assert client.post(f"/api/bookings/{booking.id}/approve", json={}).status_code == 409
