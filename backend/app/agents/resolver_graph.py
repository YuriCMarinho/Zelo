"""Nó 3: Agente Resolvedor em LangGraph (Fluxo C — Manutenção).

Implementa a máquina de estados completa de 5 passos da manutenção:
1. Coleta de Orçamentos de Prestadores Validados (com fallback Nó S)
2. Síntese Comparativa e Aprovação Humana do Anfitrião (interrupt)
3. Proposta de Datas conforme regra determinística Urgência × Agenda
4. Confirmação do Dia ("Devolutiva do Dia" com loop em caso de recusa)
5. Aviso ao Inquilino Hospedado e Fechamento do Chamado (RESOLVED)
"""

import logging
from typing import Any, TypedDict

from langgraph.checkpoint.base import BaseCheckpointSaver  # type: ignore[import-untyped]
from langgraph.checkpoint.memory import MemorySaver  # type: ignore[import-untyped]
from langgraph.graph import END, START, StateGraph  # type: ignore[import-untyped]
from langgraph.types import Command, interrupt  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.llm import generate
from app.db.models.property import Property
from app.db.models.provider import Provider
from app.db.models.quote import Quote
from app.db.models.ticket import MaintenanceTicket
from app.db.session import SessionLocal
from app.schemas.common import ProviderCategory, QuoteStatus, TicketStatus
from app.schemas.resolver import ResolutionRequest, ResolverStarter
from app.services.scheduling import find_optimal_schedule

logger = logging.getLogger("smartrepair.resolver_graph")


class ResolverState(TypedDict):
    """Estado serializável do fluxo de resolução de manutenção do Nó 3."""

    ticket_id: str
    property_id: str
    run_id: str
    category: str
    urgency: str
    location: str
    description: str
    candidate_providers: list[dict[str, Any]]
    quotes: list[dict[str, Any]]
    adm_synthesis: str
    selected_provider_id: str | None
    proposed_date: str | None
    notify_tenant: bool
    retry_date_count: int
    refuse_dates_count: int  # Usado para simular recusas de data em testes/caminhos alternativos
    status: str
    error: str | None


# -----------------------------------------------------------------------------
# Nós do Grafo de Resolução
# -----------------------------------------------------------------------------


async def dispatch_or_fallback(state: ResolverState) -> dict[str, Any]:
    """Passo 1a: Consulta prestadores validados da categoria ou aciona fallback Nó S."""
    ticket_id = state["ticket_id"]
    category_val = state["category"]
    run_id = state["run_id"]

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            return {"status": "error", "error": f"Ticket '{ticket_id}' não encontrado"}

        # Busca prestadores validados na categoria
        query = (
            select(Provider)
            .where(
                Provider.category == category_val,
                Provider.is_validated.is_(True),
            )
            .order_by(Provider.rating.desc().nullslast())
        )
        providers = db.execute(query).scalars().all()

        if not providers:
            logger.warning(
                "Nenhum prestador validado encontrado para a categoria; acionando fallback",
                extra={"run_id": run_id, "category": category_val},
            )
            ticket.status = TicketStatus.NO_PROVIDERS_FALLBACK.value
            db.commit()
            return {
                "candidate_providers": [],
                "status": TicketStatus.NO_PROVIDERS_FALLBACK.value,
            }

        # Seleciona até 3 prestadores candidatos
        candidates = [
            {
                "id": p.id,
                "name": p.name,
                "category": p.category,
                "phone": p.phone,
                "rating": p.rating,
            }
            for p in providers[:3]
        ]

        ticket.status = TicketStatus.REQUESTING_QUOTES.value
        db.commit()

        return {
            "candidate_providers": candidates,
            "status": TicketStatus.REQUESTING_QUOTES.value,
        }


async def request_and_receive_quotes(state: ResolverState) -> dict[str, Any]:
    """Passo 1b: Solicita e registra propostas de orçamentos dos prestadores selecionados."""
    ticket_id = state["ticket_id"]
    run_id = state["run_id"]
    candidates = state.get("candidate_providers", [])

    if not candidates:
        with SessionLocal() as db:
            ticket = db.get(MaintenanceTicket, ticket_id)
            if ticket:
                ticket.status = TicketStatus.ESCALATED_TO_ADM.value
                db.commit()
        return {
            "quotes": [],
            "status": TicketStatus.ESCALATED_TO_ADM.value,
            "error": "Nenhum prestador disponível para envio de orçamentos.",
        }

    quotes_recorded: list[dict[str, Any]] = []

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            return {"status": "error", "error": "Ticket não encontrado"}

        base_rate_map = {
            ProviderCategory.PLUMBER.value: 180.0,
            ProviderCategory.ELECTRICIAN.value: 220.0,
            ProviderCategory.PAINTER.value: 350.0,
            ProviderCategory.ORGANIZER.value: 150.0,
            ProviderCategory.GENERAL_MAINTENANCE.value: 200.0,
        }
        base_rate = base_rate_map.get(ticket.category, 190.0)

        for idx, provider_data in enumerate(candidates):
            # Garante persistência da cotação
            quote_query = select(Quote).where(
                Quote.ticket_id == ticket_id,
                Quote.provider_id == provider_data["id"],
            )
            quote = db.execute(quote_query).scalar_one_or_none()

            if not quote:
                quote = Quote(
                    ticket_id=ticket_id,
                    run_id=run_id,
                    provider_id=provider_data["id"],
                    status=QuoteStatus.REQUESTED.value,
                )
                db.add(quote)
                db.commit()
                db.refresh(quote)

            # Simula/gera resposta de orçamento via LLM
            prompt = [
                {
                    "role": "system",
                    "content": (
                        f"Você é o prestador {provider_data['name']} ({ticket.category}). "
                        f"Forneça orçamento profissional para o reparo em "
                        f"{ticket.location_in_property}: {ticket.description}."
                    ),
                },
                {"role": "user", "content": "Envie seu valor estimado e descrição."},
            ]
            await generate(
                messages=prompt,
                model="Qwen/Qwen3.5-4B",
                max_tokens=128,
                run_id=run_id,
                node="resolver_quote",
                db=db,
            )

            quote_val = round(base_rate + (idx * 35.0), 2)
            quote.amount = quote_val
            quote.description = f"Reparo completo de {ticket.description} com garantia de 90 dias"
            quote.proposed_availability = "Disponibilidade imediata a partir de amanhã"
            quote.status = QuoteStatus.RECEIVED.value
            db.commit()

            quotes_recorded.append(
                {
                    "id": quote.id,
                    "provider_id": quote.provider_id,
                    "provider_name": provider_data["name"],
                    "amount": quote.amount,
                    "description": quote.description,
                    "rating": provider_data.get("rating"),
                }
            )

        ticket.status = TicketStatus.AWAITING_ADM_APPROVAL.value
        db.commit()

    return {
        "quotes": quotes_recorded,
        "status": TicketStatus.AWAITING_ADM_APPROVAL.value,
    }


async def synthesize_for_adm(state: ResolverState) -> dict[str, Any]:
    """Passo 2: Apresenta síntese comparativa e aguarda escolha humana do ADM via interrupt."""
    ticket_id = state["ticket_id"]
    run_id = state["run_id"]
    quotes = state.get("quotes", [])

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        prop = db.get(Property, state["property_id"]) if ticket else None
        prop_name = prop.name if prop else "Imóvel"

        quotes_summary_lines = [
            f"- {q['provider_name']} (ID: {q['provider_id']}): "
            f"R$ {q['amount']:.2f} — {q['description']}"
            for q in quotes
        ]
        quotes_text = "\n".join(quotes_summary_lines)

        messages = [
            {
                "role": "system",
                "content": (
                    f"Você é o agente resolutivo do imóvel '{prop_name}'. "
                    "Apresente um comparativo claro, acolhedor e objetivo dos orçamentos recebidos "
                    "para que o anfitrião (ADM) tome a decisão final de contratação."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Chamado: {state['description']} ({state['location']}). "
                    f"Urgência: {state['urgency']}.\nOrçamentos disponíveis:\n{quotes_text}"
                ),
            },
        ]

        resp = await generate(
            messages=messages,
            model="Qwen/Qwen3.5-9B",
            max_tokens=320,
            run_id=run_id,
            node="resolver_adm_summary",
            temperature=0.2,
            db=db,
        )
        synthesis = resp.content

        if ticket:
            ticket.status = TicketStatus.AWAITING_ADM_APPROVAL.value
            db.commit()

    # Pausa com interrupt exigindo a seleção explícita do anfitrião
    decision = interrupt(
        {
            "action": "await_adm_approval",
            "ticket_id": ticket_id,
            "property_id": state["property_id"],
            "quotes": quotes,
            "synthesis": synthesis,
        }
    )

    selected_id: str | None = None
    if isinstance(decision, dict):
        selected_id = decision.get("selected_provider_id")
    elif isinstance(decision, str):
        selected_id = decision

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if ticket and selected_id:
            ticket.selected_provider_id = selected_id
            for q in ticket.quotes:
                if q.provider_id == selected_id:
                    q.status = QuoteStatus.SELECTED.value
                else:
                    q.status = QuoteStatus.REJECTED.value
            db.commit()

    return {
        "adm_synthesis": synthesis,
        "selected_provider_id": selected_id,
        "status": TicketStatus.PROPOSING_DATE.value,
    }


async def propose_date_and_confirm(state: ResolverState) -> dict[str, Any]:
    """Passos 3 e 4: Propõe datas por Urgência × Agenda e interpreta devolutiva do prestador."""
    ticket_id = state["ticket_id"]
    property_id = state["property_id"]
    run_id = state["run_id"]
    urgency = state["urgency"]
    retry_count = state.get("retry_date_count", 0)
    refuse_target = state.get("refuse_dates_count", 0)

    # Limite máximo de 3 tentativas de agendamento antes de escalar
    if retry_count >= 3:
        with SessionLocal() as db:
            ticket = db.get(MaintenanceTicket, ticket_id)
            if ticket:
                ticket.status = TicketStatus.ESCALATED_TO_ADM.value
                db.commit()
        return {
            "status": TicketStatus.ESCALATED_TO_ADM.value,
            "error": "Prestador recusou 3 datas propostas; escalado ao anfitrião.",
        }

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            return {"status": "error", "error": "Ticket não encontrado"}

        # Consulta regra determinística de agendamento com deslocamento de slot
        proposal = find_optimal_schedule(
            db=db,
            property_id=property_id,
            urgency=urgency,
            offset_slots=retry_count,
        )

        ticket.status = TicketStatus.WAITING_DATE_CONFIRMATION.value
        db.commit()

        # Simula comunicação de confirmação do dia via LLM
        prompt = [
            {
                "role": "system",
                "content": (
                    "Você é o prestador contratado. A data proposta para o serviço é "
                    f"{proposal.proposed_date.strftime('%d/%m/%Y às %H:%M')}. "
                    "Confirme o aceite do serviço."
                ),
            },
            {"role": "user", "content": "Você confirma a data proposta?"},
        ]
        await generate(
            messages=prompt,
            model="Qwen/Qwen3.5-4B",
            max_tokens=128,
            run_id=run_id,
            node="resolver_date_confirm",
            db=db,
        )

        # Verifica se há recusa de data programada para teste de caminhos alternativos
        if retry_count < refuse_target:
            logger.info(
                "Prestador recusou a data proposta; retornando ao Passo 3 em loop",
                extra={"retry_count": retry_count, "ticket_id": ticket_id},
            )
            return {
                "proposed_date": proposal.proposed_date.isoformat(),
                "notify_tenant": proposal.notify_tenant,
                "retry_date_count": retry_count + 1,
                "status": TicketStatus.PROPOSING_DATE.value,
            }

        # Devolutiva positiva confirmada
        ticket.status = TicketStatus.CONFIRMED_SCHEDULE.value
        ticket.scheduled_date = proposal.proposed_date
        ticket.notify_tenant = proposal.notify_tenant
        db.commit()

    return {
        "proposed_date": proposal.proposed_date.isoformat(),
        "notify_tenant": proposal.notify_tenant,
        "status": TicketStatus.CONFIRMED_SCHEDULE.value,
    }


async def notify_tenant_and_resolve(state: ResolverState) -> dict[str, Any]:
    """Passo 5: Notifica inquilino se houver hóspede na data e finaliza ticket (RESOLVED)."""
    ticket_id = state["ticket_id"]
    run_id = state["run_id"]
    notify_needed = state.get("notify_tenant", False)
    date_str = state.get("proposed_date", "")

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            return {"status": "error", "error": "Ticket não encontrado"}

        if notify_needed:
            ticket.status = TicketStatus.NOTIFYING_TENANT.value
            ticket.notify_tenant = True
            db.commit()

            prompt = [
                {
                    "role": "system",
                    "content": (
                        "Você é o assistente virtual do imóvel. Redija uma mensagem "
                        "gentil e objetiva ao hóspede informando que um prestador "
                        "realizará a manutenção agendada."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Serviço: {ticket.description}. Data/Hora confirmada: {date_str}.",
                },
            ]
            await generate(
                messages=prompt,
                model="Qwen/Qwen3.5-4B",
                max_tokens=160,
                run_id=run_id,
                node="resolver_notify_tenant",
                db=db,
            )

        ticket.status = TicketStatus.RESOLVED.value
        db.commit()

    return {"status": TicketStatus.RESOLVED.value}


# -----------------------------------------------------------------------------
# Compilação do Grafo LangGraph
# -----------------------------------------------------------------------------


def route_after_dispatch(state: ResolverState) -> str:
    if state["status"] == TicketStatus.NO_PROVIDERS_FALLBACK.value:
        return END
    return "request_and_receive_quotes"


def route_after_quotes(state: ResolverState) -> str:
    if state["status"] == TicketStatus.ESCALATED_TO_ADM.value:
        return END
    return "synthesize_for_adm"


def route_after_propose_date(state: ResolverState) -> str:
    if state["status"] == TicketStatus.PROPOSING_DATE.value:
        return "propose_date_and_confirm"
    if state["status"] == TicketStatus.ESCALATED_TO_ADM.value:
        return END
    return "notify_tenant_and_resolve"


def build_resolver_graph(checkpointer: BaseCheckpointSaver | None = None) -> Any:
    """Constrói e compila o StateGraph LangGraph para o Nó 3 com suporte a checkpointer."""
    builder = StateGraph(ResolverState)

    builder.add_node("dispatch_or_fallback", dispatch_or_fallback)
    builder.add_node("request_and_receive_quotes", request_and_receive_quotes)
    builder.add_node("synthesize_for_adm", synthesize_for_adm)
    builder.add_node("propose_date_and_confirm", propose_date_and_confirm)
    builder.add_node("notify_tenant_and_resolve", notify_tenant_and_resolve)

    builder.add_edge(START, "dispatch_or_fallback")
    builder.add_conditional_edges("dispatch_or_fallback", route_after_dispatch)
    builder.add_conditional_edges("request_and_receive_quotes", route_after_quotes)
    builder.add_edge("synthesize_for_adm", "propose_date_and_confirm")
    builder.add_conditional_edges("propose_date_and_confirm", route_after_propose_date)
    builder.add_edge("notify_tenant_and_resolve", END)

    saver = checkpointer or MemorySaver()
    return builder.compile(checkpointer=saver)


# Instância padrão em memória para execução contínua
default_checkpointer = MemorySaver()
compiled_resolver_graph = build_resolver_graph(default_checkpointer)


# -----------------------------------------------------------------------------
# Implementação Concreta do Protocolo ResolverStarter
# -----------------------------------------------------------------------------


class LangGraphResolverStarter(ResolverStarter):
    """Implementação concreta de ResolverStarter via LangGraph.

    Idempotente: Se o ticket já tiver sido iniciado, não recria nem reinicia do zero.
    """

    def __init__(self, graph: Any | None = None) -> None:
        self.graph = graph or compiled_resolver_graph

    async def astart_resolution(
        self,
        request: ResolutionRequest,
        db: Session | None = None,
        refuse_dates_count: int = 0,
    ) -> dict[str, Any]:
        """Inicia a resolução assíncrona do chamado no grafo LangGraph."""
        session_to_use = db or SessionLocal()
        close_session = db is None

        try:
            ticket = session_to_use.get(MaintenanceTicket, request.ticket_id)
            if not ticket:
                raise ValueError(f"Ticket '{request.ticket_id}' não encontrado.")

            # Idempotência: Se o ticket não estiver mais em 'open', não recomeça
            if ticket.status not in (TicketStatus.OPEN.value, "open"):
                logger.info(
                    "Ticket já em andamento ou finalizado; execução ignorada para idempotência.",
                    extra={"ticket_id": ticket.id, "status": ticket.status},
                )
                thread_config = {"configurable": {"thread_id": request.ticket_id}}
                state_snapshot = await self.graph.aget_state(thread_config)
                if state_snapshot and state_snapshot.values:
                    return dict(state_snapshot.values)
                return {}

            initial_state: ResolverState = {
                "ticket_id": ticket.id,
                "property_id": ticket.property_id,
                "run_id": request.run_id,
                "category": ticket.category,
                "urgency": ticket.urgency,
                "location": ticket.location_in_property,
                "description": ticket.description,
                "candidate_providers": [],
                "quotes": [],
                "adm_synthesis": "",
                "selected_provider_id": None,
                "proposed_date": None,
                "notify_tenant": False,
                "retry_date_count": 0,
                "refuse_dates_count": refuse_dates_count,
                "status": TicketStatus.OPEN.value,
                "error": None,
            }

            thread_config = {"configurable": {"thread_id": request.ticket_id}}
            result = await self.graph.ainvoke(initial_state, thread_config)
            return dict(result) if isinstance(result, dict) else {}

        finally:
            if close_session:
                session_to_use.close()

    def start_resolution(self, request: ResolutionRequest) -> None:
        """Método síncrono exigido pelo protocolo ResolverStarter."""
        import asyncio

        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self.astart_resolution(request))
        except RuntimeError:
            asyncio.run(self.astart_resolution(request))


async def resume_resolution(
    ticket_id: str,
    provider_id: str,
    graph: Any | None = None,
) -> Any:
    """Retoma a execução do grafo após a aprovação de orçamento pelo ADM."""
    target_graph = graph or compiled_resolver_graph
    thread_config = {"configurable": {"thread_id": ticket_id}}

    state_snapshot = await target_graph.aget_state(thread_config)
    if not state_snapshot or not state_snapshot.next:
        raise ValueError(f"O chamado '{ticket_id}' não está pausado aguardando aprovação do ADM.")

    command: Command[Any] = Command(resume={"selected_provider_id": provider_id})
    return await target_graph.ainvoke(command, thread_config)
