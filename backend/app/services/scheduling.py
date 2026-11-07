"""Serviço de agendamento inteligente baseado na regra Urgência × Agenda de Ocupação.

Lógica 100% determinística em código Python puro (custo US$ 0,00).
- Chamados urgentes: alocam o 1º horário livre mesmo se houver hóspede (notifica hóspede).
- Chamados não urgentes: preferem exclusivamente datas sem reserva ativa.
"""

from datetime import UTC, date, datetime, time, timedelta

from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.booking import Booking
from app.schemas.common import TicketUrgency


class ScheduleProposal(BaseModel):
    """Proposta de data de agendamento calculada para o prestador de serviços."""

    model_config = ConfigDict(from_attributes=True)

    proposed_date: datetime
    has_guest: bool
    notify_tenant: bool
    slot_description: str


def find_optimal_schedule(
    db: Session,
    property_id: str,
    urgency: TicketUrgency | str,
    reference_date: date | None = None,
    days_ahead: int = 14,
    offset_slots: int = 0,
) -> ScheduleProposal:
    """Calcula a data ideal de agendamento combinando nível de urgência e agenda do imóvel.

    Parâmetros:
    - db: Sessão ativa do SQLAlchemy.
    - property_id: ID do imóvel no banco.
    - urgency: 'urgent' ou 'normal' (ou enum TicketUrgency).
    - reference_date: Data base de cálculo (padrão: hoje em UTC).
    - days_ahead: Janela de dias para buscar slots sem reserva.
    - offset_slots: Deslocamento de slot (usado quando o prestador recusa a primeira data).
    """
    if reference_date is None:
        reference_date = datetime.now(UTC).date()

    urgency_str = urgency.value if isinstance(urgency, TicketUrgency) else str(urgency).lower()

    # Consulta reservas ativas/confirmadas para o imóvel a partir da data de referência
    query = (
        select(Booking)
        .where(
            Booking.property_id == property_id,
            Booking.status.in_(["confirmed", "active"]),
            Booking.end_date >= reference_date,
        )
        .order_by(Booking.start_date.asc())
    )
    bookings = db.execute(query).scalars().all()

    def is_date_occupied(check_date: date) -> bool:
        """Verifica se há hóspede no imóvel na data especificada."""
        return any(b.start_date <= check_date <= b.end_date for b in bookings)

    # 1. CASO URGENTE: O quanto antes (amanhã ou hoje + offset), mesmo com hóspede
    if urgency_str == TicketUrgency.URGENT.value:
        target_day = reference_date + timedelta(days=1 + offset_slots)
        # Horário prioritário de urgência: 09:00 UTC
        slot_time = time(hour=9, minute=0)
        proposed_dt = datetime.combine(target_day, slot_time, tzinfo=UTC)

        occupied = is_date_occupied(target_day)
        return ScheduleProposal(
            proposed_date=proposed_dt,
            has_guest=occupied,
            notify_tenant=occupied,
            slot_description=(
                f"Horário emergencial às 09:00 em {target_day.strftime('%d/%m/%Y')} "
                f"({'com hóspede — notificação obrigatória' if occupied else 'imóvel vago'})"
            ),
        )

    # 2. CASO NÃO URGENTE: Prioriza dias sem hóspede nos próximos 14 dias
    vacant_dates: list[date] = []
    for day_offset in range(1, days_ahead + 1):
        candidate_date = reference_date + timedelta(days=day_offset)
        if not is_date_occupied(candidate_date):
            vacant_dates.append(candidate_date)

    if vacant_dates:
        # Se houver dias vagos, seleciona conforme o offset (ou o último disponível)
        selected_idx = min(offset_slots, len(vacant_dates) - 1)
        selected_day = vacant_dates[selected_idx]
        slot_time = time(hour=14, minute=0)  # Período padrão da tarde para não urgentes
        proposed_dt = datetime.combine(selected_day, slot_time, tzinfo=UTC)

        return ScheduleProposal(
            proposed_date=proposed_dt,
            has_guest=False,
            notify_tenant=False,
            slot_description=(
                f"Horário regular às 14:00 em {selected_day.strftime('%d/%m/%Y')} "
                "(imóvel sem reserva ativa)"
            ),
        )

    # 3. Fallback: Se estiver 100% ocupado pelos próximos 14 dias, aloca a data mais próxima viável
    target_day = reference_date + timedelta(days=1 + offset_slots)
    slot_time = time(hour=14, minute=0)
    proposed_dt = datetime.combine(target_day, slot_time, tzinfo=UTC)

    return ScheduleProposal(
        proposed_date=proposed_dt,
        has_guest=True,
        notify_tenant=True,
        slot_description=(
            f"Horário de manutenção às 14:00 em {target_day.strftime('%d/%m/%Y')} "
            "(agenda completamente ocupada nos próximos 14 dias — hóspede será notificado)"
        ),
    )
