"""Endpoints HTTP para gestão e aprovação de chamados de manutenção (Nó 3)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.resolver_graph import resume_resolution
from app.db.models import MaintenanceTicket, Property, Quote
from app.db.session import get_db
from app.schemas.common import TicketStatus
from app.schemas.quote import QuoteRead
from app.schemas.ticket import MaintenanceTicketRead, TicketApprovalRequest

router = APIRouter(prefix="/api/tickets", tags=["Tickets"])
property_tickets_router = APIRouter(prefix="/api/properties", tags=["Imóveis"])

DatabaseDep = Annotated[Session, Depends(get_db)]


@router.get(
    "",
    response_model=list[MaintenanceTicketRead],
    summary="Listar chamados de manutenção",
    description="Retorna lista de chamados com filtros opcionais por imóvel e status.",
)
def list_tickets(
    db: DatabaseDep,
    property_id: str | None = None,
    status_filter: TicketStatus | None = None,
) -> list[MaintenanceTicket]:
    query = db.query(MaintenanceTicket)
    if property_id:
        query = query.filter(MaintenanceTicket.property_id == property_id)
    if status_filter:
        query = query.filter(MaintenanceTicket.status == status_filter.value)
    return query.order_by(MaintenanceTicket.created_at.desc()).all()


@router.get(
    "/{ticket_id}",
    response_model=MaintenanceTicketRead,
    summary="Detalhes do chamado",
    description="Obtém os dados completos de um chamado pelo identificador.",
)
def get_ticket(
    ticket_id: str,
    db: DatabaseDep,
) -> MaintenanceTicket:
    ticket = db.query(MaintenanceTicket).filter(MaintenanceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' não encontrado.",
        )
    return ticket


@router.get(
    "/{ticket_id}/quotes",
    response_model=list[QuoteRead],
    summary="Listar cotações do chamado",
    description="Retorna todas as cotações solicitadas e recebidas para o chamado.",
)
def list_ticket_quotes(
    ticket_id: str,
    db: DatabaseDep,
) -> list[Quote]:
    ticket = db.query(MaintenanceTicket).filter(MaintenanceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' não encontrado.",
        )
    return db.query(Quote).filter(Quote.ticket_id == ticket_id).all()


@router.post(
    "/{ticket_id}/approve",
    response_model=MaintenanceTicketRead,
    summary="Aprovação de orçamento pelo ADM",
    description=(
        "Permite ao administrador aprovar um orçamento para "
        "destravar a máquina de estados do Nó 3."
    ),
)
async def approve_ticket_quote(
    ticket_id: str,
    payload: TicketApprovalRequest,
    db: DatabaseDep,
) -> MaintenanceTicket:
    db.expire_all()
    ticket = db.query(MaintenanceTicket).filter(MaintenanceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' não encontrado.",
        )

    if ticket.status != TicketStatus.AWAITING_ADM_APPROVAL.value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Ticket '{ticket_id}' não está aguardando aprovação do ADM "
                f"(status atual: '{ticket.status}')."
            ),
        )

    # Verifica se a cotação escolhida existe para o chamado
    quote = (
        db.query(Quote)
        .filter(
            Quote.ticket_id == ticket_id,
            Quote.provider_id == payload.provider_id,
        )
        .first()
    )
    if not quote:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Não foi encontrada cotação do prestador '{payload.provider_id}' "
                "para este chamado."
            ),
        )

    try:
        await resume_resolution(ticket_id=ticket_id, provider_id=payload.provider_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erro ao retomar resolução do ticket: {e}",
        ) from e

    db.expire_all()
    refreshed_ticket = (
        db.query(MaintenanceTicket).filter(MaintenanceTicket.id == ticket_id).first()
    )
    if not refreshed_ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' não encontrado após atualização.",
        )
    return refreshed_ticket


@property_tickets_router.get(
    "/{property_id}/tickets",
    response_model=list[MaintenanceTicketRead],
    summary="Listar chamados de um imóvel",
    description="Retorna todos os chamados registrados para um imóvel específico.",
)
def list_tickets_for_property(
    property_id: str,
    db: DatabaseDep,
) -> list[MaintenanceTicket]:
    prop = db.query(Property).filter(Property.id == property_id).first()
    if not prop:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Imóvel '{property_id}' não encontrado.",
        )
    return (
        db.query(MaintenanceTicket)
        .filter(MaintenanceTicket.property_id == property_id)
        .order_by(MaintenanceTicket.created_at.desc())
        .all()
    )
