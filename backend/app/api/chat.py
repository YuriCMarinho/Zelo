"""Endpoint HTTP para o ponto único de chat do imóvel com isolamento por sessão e canal.

Orquestra a recepção da mensagem, aplicação de guardrails de entrada,
memória conversacional multi-turn por (property_id, session_id, channel),
roteamento entre Comercial (Nó 1) e Manutenção (Nó 2), e retorno
estruturado padronizado conforme o contrato ChatMessageOutput.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.agents.commercial import handle_commercial_message
from app.agents.router import route_chat_message
from app.agents.validator import handle_maintenance_message
from app.db.models import ChatMessageRecord, Property
from app.db.session import get_db
from app.schemas.chat import ChatHistoryItem, ChatMessageInput, ChatMessageOutput
from app.schemas.common import ReportedByRole, RouteDestination
from app.security.guardrails import SecurityViolationError

chat_router = APIRouter(tags=["Chat"])

DatabaseDep = Annotated[Session, Depends(get_db)]


def _resolve_channel(sender_role: ReportedByRole, explicit_channel: str | None) -> str:
    if explicit_channel in ("guest", "cleaner"):
        return explicit_channel
    return "cleaner" if sender_role == ReportedByRole.CLEANER else "guest"


@chat_router.get(
    "/chat/history",
    response_model=list[ChatHistoryItem],
    status_code=status.HTTP_200_OK,
    summary="Histórico de mensagens do canal e sessão",
)
def get_chat_history(
    db: DatabaseDep,
    property_id: str = Query(..., min_length=1),
    session_id: str = Query(default="default"),
    channel: str = Query(default="guest"),
) -> list[ChatHistoryItem]:
    """Retorna o histórico de mensagens isolado por imóvel, sessão e canal."""
    records = (
        db.query(ChatMessageRecord)
        .filter(
            ChatMessageRecord.property_id == property_id,
            ChatMessageRecord.session_id == session_id,
            ChatMessageRecord.channel == channel,
        )
        .order_by(ChatMessageRecord.created_at.asc(), ChatMessageRecord.id.asc())
        .all()
    )
    return [ChatHistoryItem.model_validate(r) for r in records]


@chat_router.post(
    "/chat",
    response_model=ChatMessageOutput,
    status_code=status.HTTP_200_OK,
    summary="Ponto único de chat do imóvel",
    description="Processa mensagens de hóspedes ou camareiras e as encaminha ao Nó 1 ou Nó 2.",
)
async def process_chat_message(
    input_data: ChatMessageInput,
    db: DatabaseDep,
) -> ChatMessageOutput:
    """Recebe mensagem do chat, valida guardrails e executa o fluxo comercial ou de manutenção."""
    # 1. Garante run_id e session_id ponta a ponta
    if not input_data.run_id or not input_data.run_id.strip():
        run_id = f"run-chat-{uuid.uuid4().hex[:8]}"
    else:
        run_id = input_data.run_id.strip()

    session_id = (input_data.session_id or "default").strip() or "default"
    channel = _resolve_channel(input_data.sender_role, input_data.channel)

    # 2. Localiza o imóvel no banco de dados
    prop = db.query(Property).filter(Property.id == input_data.property_id).first()
    if prop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Imóvel com id '{input_data.property_id}' não encontrado.",
        )

    # 3. Carrega histórico recente da sessão e canal para memória multi-turn
    recent_records = (
        db.query(ChatMessageRecord)
        .filter(
            ChatMessageRecord.property_id == prop.id,
            ChatMessageRecord.session_id == session_id,
            ChatMessageRecord.channel == channel,
        )
        .order_by(ChatMessageRecord.created_at.desc())
        .limit(8)
        .all()
    )
    history = [
        {
            "role": "assistant" if r.sender == "agent" else "user",
            "content": r.body,
        }
        for r in reversed(recent_records)
    ]

    # 4. Roteia aplicando guardrails de entrada e contexto multi-turn
    try:
        destination = await route_chat_message(
            property_id=prop.id,
            message=input_data.message,
            sender_role=input_data.sender_role,
            run_id=run_id,
            db=db,
            history=history,
        )
    except SecurityViolationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Violação de segurança nos guardrails: {err}",
        ) from err

    sender_label = "camareira" if input_data.sender_role == ReportedByRole.CLEANER else "hospede"
    user_record = ChatMessageRecord(
        property_id=prop.id,
        session_id=session_id,
        channel=channel,
        sender=sender_label,
        body=input_data.message.strip(),
    )
    db.add(user_record)
    db.commit()

    # 5. Executa o nó especializado correspondente
    if destination == RouteDestination.COMMERCIAL_NODE1:
        output = await handle_commercial_message(
            prop=prop,
            message=input_data.message,
            run_id=run_id,
            db=db,
            session_id=session_id,
            history=history,
        )
        output.channel = channel
        output.session_id = session_id

        agent_record = ChatMessageRecord(
            property_id=prop.id,
            session_id=session_id,
            channel=channel,
            sender="agent",
            body=output.response_text,
            booking_id=output.booking_id,
        )
        db.add(agent_record)
        db.commit()
        return output

    # Destino Nó 2 — Manutenção
    response_text, ticket_id = await handle_maintenance_message(
        prop=prop,
        message=input_data.message,
        sender_role=input_data.sender_role,
        run_id=run_id,
        db=db,
        history=history,
    )

    if ticket_id is not None:
        try:
            from app.agents.resolver_graph import (
                LangGraphResolverStarter,
                compiled_resolver_graph,
            )
            from app.schemas.resolver import ResolutionRequest

            starter = LangGraphResolverStarter(compiled_resolver_graph)
            req = ResolutionRequest(
                ticket_id=ticket_id,
                run_id=run_id,
            )
            await starter.astart_resolution(req, db=db)
        except Exception as err:
            import logging

            logging.getLogger(__name__).warning("Falha ao iniciar Nó 3 automaticamente: %s", err)

    suggested = (
        ["Acompanhar status do chamado", "Enviar foto ou detalhe adicional"]
        if ticket_id is not None
        else ["Informar cômodo e item com defeito", "Descrever gravidade do problema"]
    )

    agent_record = ChatMessageRecord(
        property_id=prop.id,
        session_id=session_id,
        channel=channel,
        sender="agent",
        body=response_text,
        ticket_id=ticket_id,
    )
    db.add(agent_record)
    db.commit()

    return ChatMessageOutput(
        run_id=run_id,
        property_id=prop.id,
        route_destination=RouteDestination.MAINTENANCE_NODE2,
        response_text=response_text,
        ticket_id=ticket_id,
        session_id=session_id,
        channel=channel,
        suggested_actions=suggested,
    )
