"""Endpoint HTTP para o ponto único de chat do imóvel.

Orquestra a recepção da mensagem, aplicação de guardrails de entrada,
roteamento entre Comercial (Nó 1) e Manutenção (Nó 2), e retorno
estruturado padronizado conforme o contrato ChatMessageOutput.
"""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agents.commercial import handle_commercial_message
from app.agents.router import route_chat_message
from app.agents.validator import handle_maintenance_message
from app.db.models import Property
from app.db.session import get_db
from app.schemas.chat import ChatMessageInput, ChatMessageOutput
from app.schemas.common import RouteDestination
from app.security.guardrails import SecurityViolationError

chat_router = APIRouter(tags=["Chat"])

DatabaseDep = Annotated[Session, Depends(get_db)]


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
    # 1. Garante run_id ponta a ponta
    if not input_data.run_id or not input_data.run_id.strip():
        run_id = f"run-chat-{uuid.uuid4().hex[:8]}"
    else:
        run_id = input_data.run_id.strip()

    # 2. Localiza o imóvel no banco de dados
    prop = db.query(Property).filter(Property.id == input_data.property_id).first()
    if prop is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Imóvel com id '{input_data.property_id}' não encontrado.",
        )

    # 3. Roteia aplicando guardrails de entrada
    try:
        destination = await route_chat_message(
            property_id=prop.id,
            message=input_data.message,
            sender_role=input_data.sender_role,
            run_id=run_id,
            db=db,
        )
    except SecurityViolationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Violação de segurança nos guardrails: {err}",
        ) from err

    # 4. Executa o nó especializado correspondente
    if destination == RouteDestination.COMMERCIAL_NODE1:
        return await handle_commercial_message(
            prop=prop,
            message=input_data.message,
            run_id=run_id,
            db=db,
        )

    # Destino Nó 2 — Manutenção
    response_text, ticket_id = await handle_maintenance_message(
        prop=prop,
        message=input_data.message,
        sender_role=input_data.sender_role,
        run_id=run_id,
        db=db,
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
                property_id=prop.id,
                run_id=run_id,
            )
            await starter.astart_resolution(req, db=db)
        except Exception as exc:
            import logging

            logging.getLogger("smartrepair.chat").warning(
                "Falha ao iniciar resolução automática do ticket %s: %s", ticket_id, exc
            )

    suggested_actions = (
        ["Acompanhar chamado de manutenção", "Ver status do reparo"]
        if ticket_id is not None
        else ["Informar cômodo e detalhes", "Enviar mais informações"]
    )

    return ChatMessageOutput(
        run_id=run_id,
        property_id=prop.id,
        route_destination=RouteDestination.MAINTENANCE_NODE2,
        response_text=response_text,
        ticket_id=ticket_id,
        suggested_actions=suggested_actions,
    )
