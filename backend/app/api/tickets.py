"""Endpoints HTTP para gestão e aprovação de chamados de manutenção (Nó 3)."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.resolver_graph import (
    record_date_response,
    record_quote_response,
    resume_resolution,
    retry_provider_collection,
)
from app.db.models import MaintenanceTicket, Property, Quote
from app.db.session import get_db
from app.schemas.common import QuoteStatus, TicketStatus
from app.schemas.quote import QuoteRead
from app.schemas.resolver import ProviderDateReply, ProviderQuoteReply
from app.schemas.ticket import MaintenanceTicketRead, TicketApprovalRequest
from app.security.guardrails import SecurityViolationError

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
) -> list[QuoteRead]:
    ticket = db.query(MaintenanceTicket).filter(MaintenanceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' não encontrado.",
        )
    quotes = db.query(Quote).filter(Quote.ticket_id == ticket_id).all()
    return [
        QuoteRead(
            id=q.id,
            ticket_id=q.ticket_id,
            run_id=q.run_id,
            provider_id=q.provider_id,
            amount=q.amount,
            description=q.description,
            proposed_availability=q.proposed_availability,
            status=QuoteStatus(q.status),
            created_at=q.created_at,
            provider_name=q.provider.name if q.provider else None,
            provider_rating=q.provider.rating if q.provider else None,
        )
        for q in quotes
    ]


@router.post(
    "/{ticket_id}/start-resolution",
    response_model=MaintenanceTicketRead,
    summary="Iniciar resolução do chamado (Nó 3)",
    description="Dispara a coleta de orçamentos e síntese do Nó 3 para o chamado.",
)
async def start_ticket_resolution(
    ticket_id: str,
    db: DatabaseDep,
) -> MaintenanceTicket:
    db.expire_all()
    ticket = db.query(MaintenanceTicket).filter(MaintenanceTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' não encontrado.",
        )

    # Sem prestadores: dispara de novo a coleta sob demanda do Nó S (retoma se encontrar)
    if ticket.status == TicketStatus.NO_PROVIDERS_FALLBACK.value:
        await retry_provider_collection(ticket_id)
        db.expire_all()
        return db.get(MaintenanceTicket, ticket_id) or ticket

    # Se já estiver em andamento ou finalizado, apenas retorna o ticket atual
    if ticket.status != TicketStatus.OPEN.value:
        return ticket

    from app.agents.resolver_graph import LangGraphResolverStarter, compiled_resolver_graph
    from app.schemas.resolver import ResolutionRequest

    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(
        ticket_id=ticket.id,
        run_id=ticket.run_id,
    )
    await starter.astart_resolution(req, db=db)
    db.expire_all()
    refreshed = db.query(MaintenanceTicket).filter(MaintenanceTicket.id == ticket_id).first()
    return refreshed or ticket


@router.post(
    "/{ticket_id}/approve",
    response_model=MaintenanceTicketRead,
    summary="Aprovação de orçamento pelo ADM",
    description=(
        "Permite ao administrador aprovar um orçamento para destravar a máquina de estados do Nó 3."
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
    refreshed_ticket = db.query(MaintenanceTicket).filter(MaintenanceTicket.id == ticket_id).first()
    if not refreshed_ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' não encontrado após atualização.",
        )
    return refreshed_ticket


def _refreshed(db: Session, ticket_id: str) -> MaintenanceTicket:
    db.expire_all()
    ticket = db.get(MaintenanceTicket, ticket_id)
    if not ticket:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket '{ticket_id}' não encontrado.",
        )
    return ticket


@router.post(
    "/{ticket_id}/quotes/{provider_id}/response",
    response_model=MaintenanceTicketRead,
    summary="Resposta de orçamento do prestador",
    description=(
        "Registra o orçamento enviado por um prestador (canal simulado/allowlist). "
        "Quando todos respondem, o Nó 3 segue para a síntese do ADM."
    ),
)
async def provider_quote_response(
    ticket_id: str,
    provider_id: str,
    payload: ProviderQuoteReply,
    db: DatabaseDep,
) -> MaintenanceTicket:
    _refreshed(db, ticket_id)
    try:
        await record_quote_response(
            ticket_id=ticket_id,
            provider_id=provider_id,
            amount=payload.amount,
            description=payload.description,
            availability=payload.proposed_availability,
        )
    except SecurityViolationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Violação de segurança nos guardrails: {e}",
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return _refreshed(db, ticket_id)


@router.post(
    "/{ticket_id}/date-response",
    response_model=MaintenanceTicketRead,
    summary="Devolutiva do dia do prestador",
    description=(
        "O prestador escolhido aceita ou recusa a data proposta. "
        "Recusa volta ao passo 3; aceite confirma o agendamento."
    ),
)
async def provider_date_response(
    ticket_id: str,
    payload: ProviderDateReply,
    db: DatabaseDep,
) -> MaintenanceTicket:
    _refreshed(db, ticket_id)
    try:
        await record_date_response(
            ticket_id=ticket_id, accepted=payload.accepted, message=payload.message
        )
    except SecurityViolationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Violação de segurança nos guardrails: {e}",
        ) from e
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return _refreshed(db, ticket_id)


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
