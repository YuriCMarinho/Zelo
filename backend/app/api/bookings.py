"""Endpoints HTTP para governança de reservas e decisão do anfitrião.

Permite listar reservas de cada imóvel (incluindo solicitações 'pending_approval'),
aprovar hospedagens pelo valor acordado (R$ X) ou recusar com justificativa,
disparando notificação automática no canal de chat da sessão do hóspede.
"""

import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agents.commercial import _format_brl
from app.db.models import AuditEvent, Booking, ChatMessageRecord, Property
from app.db.session import get_db
from app.schemas.booking import (
    BookingApproveRequest,
    BookingCreate,
    BookingRead,
    BookingRejectRequest,
)
from app.security.guardrails import SecurityViolationError, validate_untrusted_input

bookings_router = APIRouter(prefix="/api", tags=["Reservas"])

DatabaseDep = Annotated[Session, Depends(get_db)]

RUN_ID_FROM_NOTES_PATTERN = re.compile(r"run_id:\s*([A-Za-z0-9_-]+)")


def _resolve_booking_run_id(booking: Booking, fallback_prefix: str) -> str:
    """Extrai o run_id original registrado nas notas da reserva ou gera fallback."""
    if booking.notes:
        match = RUN_ID_FROM_NOTES_PATTERN.search(booking.notes)
        if match:
            return match.group(1)
    return f"{fallback_prefix}-{booking.id[:8]}"


def _sanitize_field(value: str | None, role: str, run_id: str) -> str | None:
    """Aplica guardrail contra prompt injection em campos textuais de reserva."""
    if value is None or not value.strip():
        return value
    try:
        return validate_untrusted_input(value, role=role, run_id=run_id)
    except SecurityViolationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@bookings_router.get(
    "/bookings",
    response_model=list[BookingRead],
    summary="Lista reservas e solicitações de hospedagem",
)
def list_bookings(
    db: DatabaseDep,
    property_id: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
) -> list[BookingRead]:
    query = db.query(Booking)
    if property_id:
        query = query.filter(Booking.property_id == property_id)
    if status_filter:
        query = query.filter(Booking.status == status_filter)
    records = query.order_by(Booking.start_date.asc(), Booking.created_at.desc()).all()
    return [BookingRead.model_validate(b) for b in records]


@bookings_router.get(
    "/properties/{property_id}/bookings",
    response_model=list[BookingRead],
    summary="Lista reservas de um imóvel específico",
)
def list_property_bookings(
    property_id: str,
    db: DatabaseDep,
) -> list[BookingRead]:
    prop = db.query(Property).filter(Property.id == property_id).first()
    if prop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Imóvel '{property_id}' não encontrado.",
        )
    records = (
        db.query(Booking)
        .filter(Booking.property_id == property_id)
        .order_by(Booking.start_date.asc(), Booking.created_at.desc())
        .all()
    )
    return [BookingRead.model_validate(b) for b in records]


@bookings_router.post(
    "/bookings",
    response_model=BookingRead,
    status_code=status.HTTP_201_CREATED,
    summary="Cria uma reserva ou solicitação diretamente",
)
def create_booking(
    payload: BookingCreate,
    db: DatabaseDep,
) -> BookingRead:
    prop = db.query(Property).filter(Property.id == payload.property_id).first()
    if prop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Imóvel '{payload.property_id}' não encontrado.",
        )

    conflict = (
        db.query(Booking)
        .filter(
            Booking.property_id == payload.property_id,
            Booking.status.in_(["confirmed", "active"]),
            Booking.start_date < payload.end_date,
            Booking.end_date > payload.start_date,
        )
        .first()
    )
    if conflict:
        c_start = conflict.start_date.strftime("%d/%m/%Y")
        c_end = conflict.end_date.strftime("%d/%m/%Y")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Conflito de agenda: já existe reserva confirmada entre {c_start} e {c_end}.",
        )

    run_id = f"run-book-create-{payload.property_id[:8]}"
    safe_guest_name = _sanitize_field(payload.guest_name, "tenant", run_id) or payload.guest_name
    safe_guest_contact = _sanitize_field(payload.guest_contact, "tenant", run_id)
    safe_notes = _sanitize_field(payload.notes, "tenant", run_id)

    nights = max(1, (payload.end_date - payload.start_date).days)
    nightly_rate = getattr(prop, "nightly_rate", 350.0) or 350.0
    total_price = (
        payload.total_price if payload.total_price is not None else round(nights * nightly_rate, 2)
    )

    booking = Booking(
        property_id=payload.property_id,
        guest_name=safe_guest_name,
        guest_contact=safe_guest_contact,
        start_date=payload.start_date,
        end_date=payload.end_date,
        status=payload.status,
        total_price=total_price,
        num_guests=payload.num_guests,
        session_id=payload.session_id or "default",
        notes=safe_notes,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return BookingRead.model_validate(booking)


@bookings_router.post(
    "/bookings/{booking_id}/approve",
    response_model=BookingRead,
    summary="Anfitrião aprova a solicitação de reserva pelo valor acordado",
)
def approve_booking(
    booking_id: str,
    db: DatabaseDep,
    payload: BookingApproveRequest | None = None,
) -> BookingRead:
    booking = db.query(Booking).filter(Booking.id == booking_id).with_for_update().first()
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reserva '{booking_id}' não encontrada.",
        )

    if booking.status in ("confirmed", "active"):
        if (
            payload
            and payload.final_price is not None
            and payload.final_price != booking.total_price
        ):
            raise HTTPException(status_code=409, detail="Reserva já aprovada com outro valor.")
        return BookingRead.model_validate(booking)
    if booking.status != "pending_approval":
        raise HTTPException(
            status_code=409, detail="Somente solicitações pendentes podem ser aprovadas."
        )

    # Serializa aprovações do mesmo imóvel, inclusive para reservas diferentes.
    prop = db.query(Property).filter(Property.id == booking.property_id).with_for_update().first()
    prop_name = prop.name if prop else booking.property_id

    # Verifica se outra reserva confirmada ocupou as datas enquanto estava pendente
    conflict = (
        db.query(Booking)
        .filter(
            Booking.property_id == booking.property_id,
            Booking.id != booking.id,
            Booking.status.in_(["confirmed", "active"]),
            Booking.start_date < booking.end_date,
            Booking.end_date > booking.start_date,
        )
        .first()
    )
    if conflict:
        c_start = conflict.start_date.strftime("%d/%m/%Y")
        c_end = conflict.end_date.strftime("%d/%m/%Y")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Não é possível aprovar: já existe outra reserva confirmada de "
                f"{c_start} a {c_end}."
            ),
        )

    run_id = _resolve_booking_run_id(booking, "run-book-approve")
    nights = max(1, (booking.end_date - booking.start_date).days)
    nightly_rate = getattr(prop, "nightly_rate", 350.0) if prop else 350.0
    final_price = (
        payload.final_price
        if payload and payload.final_price is not None
        else (booking.total_price or round(nights * nightly_rate, 2))
    )

    booking.status = "confirmed"
    booking.total_price = final_price
    booking.rejection_reason = None
    if payload and payload.host_notes:
        safe_host_notes = _sanitize_field(payload.host_notes, "admin", run_id)
        booking.notes = f"{booking.notes or ''} | Nota do anfitrião: {safe_host_notes}".strip(" |")

    diarias_lbl = "diária" if nights == 1 else "diárias"
    s_fmt = booking.start_date.strftime("%d/%m/%Y")
    e_fmt = booking.end_date.strftime("%d/%m/%Y")
    notification_text = (
        f"Excelente notícia! O anfitrião aprovou sua reserva para o imóvel '{prop_name}' "
        f"de {s_fmt} a {e_fmt} ({nights} {diarias_lbl}) pelo valor de "
        f"{_format_brl(final_price)}. Sua estadia está confirmada! "
        "Você já pode consultar as regras e horários de check-in por aqui."
    )

    chat_msg = ChatMessageRecord(
        property_id=booking.property_id,
        session_id=booking.session_id or "default",
        channel="guest",
        sender="agent",
        body=notification_text,
        booking_id=booking.id,
    )
    db.add(chat_msg)

    audit = AuditEvent(
        run_id=run_id,
        ticket_id=None,
        node="commercial_governance",
        event_type="booking_approved",
        payload={
            "booking_id": booking.id,
            "property_id": booking.property_id,
            "guest_ref": f"guest-{booking.id[:8]}",
            "start_date": booking.start_date.isoformat(),
            "end_date": booking.end_date.isoformat(),
            "total_price": final_price,
            "session_id": booking.session_id or "default",
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(booking)
    return BookingRead.model_validate(booking)


@bookings_router.post(
    "/bookings/{booking_id}/reject",
    response_model=BookingRead,
    summary="Anfitrião recusa a solicitação de reserva informando o motivo",
)
def reject_booking(
    booking_id: str,
    payload: BookingRejectRequest,
    db: DatabaseDep,
) -> BookingRead:
    booking = db.query(Booking).filter(Booking.id == booking_id).with_for_update().first()
    if booking is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reserva '{booking_id}' não encontrada.",
        )

    if booking.status == "rejected":
        return BookingRead.model_validate(booking)
    if booking.status != "pending_approval":
        raise HTTPException(
            status_code=409, detail="Somente solicitações pendentes podem ser recusadas."
        )

    run_id = _resolve_booking_run_id(booking, "run-book-reject")
    prop = db.query(Property).filter(Property.id == booking.property_id).first()
    prop_name = prop.name if prop else booking.property_id
    reason = _sanitize_field(payload.reason.strip(), "admin", run_id) or payload.reason.strip()

    booking.status = "rejected"
    booking.rejection_reason = reason

    s_fmt = booking.start_date.strftime("%d/%m/%Y")
    e_fmt = booking.end_date.strftime("%d/%m/%Y")
    notification_text = (
        f"Atualização sobre sua solicitação para '{prop_name}' ({s_fmt} a {e_fmt}): "
        "o anfitrião não pôde aceitar a reserva para este período. "
        f"Motivo informado: {reason}. "
        "Gostaria de verificar outras datas disponíveis no calendário?"
    )

    chat_msg = ChatMessageRecord(
        property_id=booking.property_id,
        session_id=booking.session_id or "default",
        channel="guest",
        sender="agent",
        body=notification_text,
        booking_id=booking.id,
    )
    db.add(chat_msg)

    audit = AuditEvent(
        run_id=run_id,
        ticket_id=None,
        node="commercial_governance",
        event_type="booking_rejected",
        payload={
            "booking_id": booking.id,
            "property_id": booking.property_id,
            "guest_ref": f"guest-{booking.id[:8]}",
            "start_date": booking.start_date.isoformat(),
            "end_date": booking.end_date.isoformat(),
            "rejection_reason": reason,
            "session_id": booking.session_id or "default",
        },
    )
    db.add(audit)
    db.commit()
    db.refresh(booking)
    return BookingRead.model_validate(booking)
