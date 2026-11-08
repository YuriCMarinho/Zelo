"""Nó 3: Agente Resolvedor em LangGraph (Fluxo C — Manutenção).

Máquina de estados de 5 passos (docs/PLAN.md §2 e §3). Cada espera é um `interrupt`
retomado por um evento externo real, nunca simulado pelo LLM:

1. Orçamentos: pede a N prestadores validados da categoria/região e espera as respostas
   (endpoint do prestador/simulador) ou o timeout. Sem prestador, aciona o Nó S em
   segundo plano e espera a coleta (fallback assíncrono).
2. ADM: síntese comparativa e espera a escolha explícita do anfitrião.
3. Data: regra determinística Urgência × Agenda.
4. Devolutiva do dia: espera o prestador aceitar ou recusar (recusa volta ao passo 3).
5. Aviso ao inquilino hospedado (registrado no imóvel) e fechamento do chamado.

Toda mudança de status passa por `is_valid_ticket_transition`.
"""

import asyncio
import logging
from collections.abc import Coroutine
from datetime import datetime
from typing import TYPE_CHECKING, Any, TypedDict, cast

from langgraph.checkpoint.base import BaseCheckpointSaver  # type: ignore[import-untyped]
from langgraph.checkpoint.memory import MemorySaver  # type: ignore[import-untyped]
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver  # type: ignore[import-untyped]
from langgraph.graph import END, START, StateGraph  # type: ignore[import-untyped]
from langgraph.types import Command, interrupt  # type: ignore[import-untyped]
from psycopg.rows import dict_row  # type: ignore[import-untyped]
from psycopg_pool import AsyncConnectionPool  # type: ignore[import-untyped]
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.resolver_timeouts import (
    cancel_timeout_job,
    register_adm_reminder,
    register_date_timeout,
    register_provider_collection_timeout,
    register_quote_timeout,
)
from app.core.config import settings
from app.core.llm import generate
from app.db.models.audit import AuditEvent
from app.db.models.property import Property
from app.db.models.provider import Provider
from app.db.models.quote import Quote
from app.db.models.ticket import MaintenanceTicket
from app.db.session import SessionLocal
from app.schemas.common import (
    ProviderCategory,
    QuoteStatus,
    TicketStatus,
    is_valid_ticket_transition,
)
from app.schemas.resolver import ResolutionRequest, ResolverStarter
from app.security.guardrails import validate_untrusted_input
from app.security.masking import mask_pii
from app.services.provider_collector import collect_on_demand
from app.services.scheduling import find_optimal_schedule

logger = logging.getLogger("smartrepair.resolver_graph")

MAX_QUOTE_CANDIDATES = 3
MAX_DATE_ATTEMPTS = 3
QUOTE_TIMEOUT_MINUTES = 60
ADM_REMINDER_MINUTES = 120
DATE_TIMEOUT_MINUTES = 120
PROVIDER_COLLECTION_TIMEOUT_MINUTES = 240


class InvalidTicketTransitionError(RuntimeError):
    """Tentativa de mudar o status do ticket fora da máquina de estados do PLAN."""


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
    status: str
    error: str | None


# -----------------------------------------------------------------------------
# Utilitários
# -----------------------------------------------------------------------------

# Referências fortes às tarefas em segundo plano (evita coleta pelo GC).
_background_tasks: set[asyncio.Task[Any]] = set()


def _spawn(coro: Coroutine[Any, Any, Any]) -> None:
    """Agenda uma corrotina em segundo plano mantendo referência até terminar."""
    task = asyncio.get_running_loop().create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def _set_status(ticket: MaintenanceTicket, new: TicketStatus) -> None:
    """Muda o status respeitando TICKET_TRANSITIONS (repetir o mesmo status é permitido)."""
    current = TicketStatus(ticket.status)
    if current != new and not is_valid_ticket_transition(current, new):
        raise InvalidTicketTransitionError(
            f"Transição inválida do ticket {ticket.id}: {current.value} -> {new.value}"
        )
    ticket.status = new.value


def _audit(
    db: Session,
    run_id: str,
    ticket_id: str,
    node: str,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    db.add(
        AuditEvent(
            run_id=run_id,
            ticket_id=ticket_id,
            node=node,
            event_type=event_type,
            payload=payload,
        )
    )


def _escalate(
    db: Session, ticket: MaintenanceTicket, run_id: str, node: str, reason: str
) -> dict[str, Any]:
    _set_status(ticket, TicketStatus.ESCALATED_TO_ADM)
    _audit(db, run_id, ticket.id, node, "escalated_to_adm", {"reason": reason})
    db.commit()
    logger.warning(
        "Chamado escalado ao ADM",
        extra={"ticket_id": ticket.id, "run_id": run_id, "reason": reason},
    )
    return {"status": TicketStatus.ESCALATED_TO_ADM.value, "error": reason}


def _region_of(db: Session, property_id: str) -> str | None:
    prop = db.get(Property, property_id)
    return prop.city if prop and prop.city else None


def _validated_providers(db: Session, category: str, city: str | None) -> list[Provider]:
    query = select(Provider).where(
        Provider.category == category,
        Provider.is_validated.is_(True),
    )
    if city:
        query = query.where(Provider.region.ilike(f"{city}%"))
    query = query.order_by(Provider.rating.desc().nullslast())
    return list(db.execute(query).scalars().all())


def _event(value: Any) -> str | None:
    return value.get("event") if isinstance(value, dict) else None


# -----------------------------------------------------------------------------
# Passo 1 — Prestadores e orçamentos
# -----------------------------------------------------------------------------


async def dispatch_or_fallback(state: ResolverState) -> dict[str, Any]:
    """Seleciona prestadores validados da categoria/região ou aciona o fallback do Nó S."""
    ticket_id = state["ticket_id"]
    run_id = state["run_id"]

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            return {"status": "error", "error": f"Ticket '{ticket_id}' não encontrado"}

        city = _region_of(db, state["property_id"])
        providers = _validated_providers(db, state["category"], city)

        if not providers:
            if ticket.status == TicketStatus.NO_PROVIDERS_FALLBACK.value:
                return _escalate(
                    db,
                    ticket,
                    run_id,
                    "dispatch_or_fallback",
                    "Coleta sob demanda terminou sem prestador validado.",
                )
            _set_status(ticket, TicketStatus.NO_PROVIDERS_FALLBACK)
            _audit(
                db,
                run_id,
                ticket_id,
                "dispatch_or_fallback",
                "no_providers_fallback",
                {"category": state["category"], "region": city, "notified_adm": True},
            )
            db.commit()
            register_provider_collection_timeout(
                ticket_id=ticket_id,
                run_id=run_id,
                timeout_minutes=PROVIDER_COLLECTION_TIMEOUT_MINUTES,
                callback=on_provider_collection_timeout,
            )
            return {"candidate_providers": [], "status": TicketStatus.NO_PROVIDERS_FALLBACK.value}

        cancel_timeout_job(f"timeout_providers_{ticket_id}")
        _set_status(ticket, TicketStatus.REQUESTING_QUOTES)
        db.commit()

        # Telefones ficam só no banco (LGPD): o estado do grafo guarda apenas ids e nomes.
        candidates = [
            {"id": p.id, "name": p.name, "rating": p.rating}
            for p in providers[:MAX_QUOTE_CANDIDATES]
        ]
        return {"candidate_providers": candidates, "status": TicketStatus.REQUESTING_QUOTES.value}


async def wait_for_providers(state: ResolverState) -> dict[str, Any]:
    """Espera a coleta sob demanda do Nó S (providers_ready) ou o timeout."""
    event = interrupt({"action": "await_providers", "ticket_id": state["ticket_id"]})
    if _event(event) == "providers_ready":
        return {"status": TicketStatus.NO_PROVIDERS_FALLBACK.value, "error": None}

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, state["ticket_id"])
        if not ticket:
            return {"status": "error", "error": "Ticket não encontrado"}
        return _escalate(
            db,
            ticket,
            state["run_id"],
            "wait_for_providers",
            "Timeout da coleta sob demanda sem prestador confirmado.",
        )


async def request_quotes(state: ResolverState) -> dict[str, Any]:
    """Registra os pedidos de orçamento (sem negociar preço) e inicia o timer de espera."""
    ticket_id = state["ticket_id"]
    run_id = state["run_id"]

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            return {"status": "error", "error": "Ticket não encontrado"}

        for provider in state["candidate_providers"]:
            exists = db.execute(
                select(Quote.id).where(
                    Quote.ticket_id == ticket_id, Quote.provider_id == provider["id"]
                )
            ).first()
            if exists is None:
                db.add(
                    Quote(
                        ticket_id=ticket_id,
                        run_id=run_id,
                        provider_id=provider["id"],
                        status=QuoteStatus.REQUESTED.value,
                    )
                )
            # Canal simulado/allowlist: registra a mensagem enviada (sem telefone).
            _audit(
                db,
                run_id,
                ticket_id,
                "request_quotes",
                "provider_message_sent",
                {
                    "provider_id": provider["id"],
                    "kind": "quote_request",
                    "text": (
                        f"Olá, {provider['name']}! Pode enviar um orçamento para "
                        f"{ticket.description} ({ticket.location_in_property})?"
                    ),
                },
            )

        _set_status(ticket, TicketStatus.WAITING_QUOTES)
        db.commit()

    register_quote_timeout(
        ticket_id=ticket_id,
        run_id=run_id,
        timeout_minutes=QUOTE_TIMEOUT_MINUTES,
        callback=on_quote_timeout,
    )
    return {"status": TicketStatus.WAITING_QUOTES.value}


async def wait_for_quotes(state: ResolverState) -> dict[str, Any]:
    """Espera todas as respostas (quotes_ready) ou o timeout; segue com as recebidas."""
    ticket_id = state["ticket_id"]
    interrupt({"action": "await_quotes", "ticket_id": ticket_id})
    cancel_timeout_job(f"timeout_quote_{ticket_id}")

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            return {"status": "error", "error": "Ticket não encontrado"}

        received: list[dict[str, Any]] = []
        for quote in ticket.quotes:
            if quote.status == QuoteStatus.REQUESTED.value:
                quote.status = QuoteStatus.TIMEOUT.value
            elif quote.status == QuoteStatus.RECEIVED.value:
                received.append(
                    {
                        "id": quote.id,
                        "provider_id": quote.provider_id,
                        "provider_name": quote.provider.name if quote.provider else None,
                        "amount": quote.amount,
                        "description": quote.description,
                        "rating": quote.provider.rating if quote.provider else None,
                    }
                )
        db.commit()

        if not received:
            return _escalate(
                db,
                ticket,
                state["run_id"],
                "wait_for_quotes",
                "Nenhum prestador respondeu ao pedido de orçamento no prazo.",
            )

    return {"quotes": received, "status": TicketStatus.WAITING_QUOTES.value}


# -----------------------------------------------------------------------------
# Passo 2 — Decisão do ADM
# -----------------------------------------------------------------------------


async def synthesize_for_adm(state: ResolverState) -> dict[str, Any]:
    """Gera a síntese comparativa e avisa o ADM na sessão do imóvel."""
    ticket_id = state["ticket_id"]
    run_id = state["run_id"]

    quotes_text = "\n".join(
        f"- {q['provider_name']} (ID: {q['provider_id']}): "
        f"R$ {q['amount']:.2f} — {q['description']}"
        for q in state["quotes"]
    )

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            return {"status": "error", "error": "Ticket não encontrado"}
        prop = db.get(Property, state["property_id"])
        prop_name = prop.name if prop else "Imóvel"

        resp = await generate(
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Você é o agente resolutivo do imóvel '{prop_name}'. Apresente um "
                        "comparativo claro e objetivo dos orçamentos recebidos para que o "
                        "anfitrião (ADM) tome a decisão final. Não escolha por ele."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Chamado: {state['description']} ({state['location']}). "
                        f"Urgência: {state['urgency']}.\nOrçamentos recebidos:\n{quotes_text}"
                    ),
                },
            ],
            model="Qwen/Qwen3.5-9B",
            max_tokens=320,
            run_id=run_id,
            node="resolver_adm_summary",
            temperature=0.2,
            db=db,
        )

        _set_status(ticket, TicketStatus.AWAITING_ADM_APPROVAL)
        _audit(
            db,
            run_id,
            ticket_id,
            "synthesize_for_adm",
            "adm_notified",
            {"synthesis": mask_pii(resp.content), "quotes": len(state["quotes"])},
        )
        db.commit()

    register_adm_reminder(
        ticket_id=ticket_id,
        run_id=run_id,
        reminder_minutes=ADM_REMINDER_MINUTES,
        callback=on_adm_reminder,
    )
    return {"adm_synthesis": resp.content, "status": TicketStatus.AWAITING_ADM_APPROVAL.value}


async def wait_for_adm(state: ResolverState) -> dict[str, Any]:
    """Espera a escolha explícita do ADM; só aceita prestador com orçamento recebido."""
    ticket_id = state["ticket_id"]
    decision = interrupt(
        {
            "action": "await_adm_approval",
            "ticket_id": ticket_id,
            "property_id": state["property_id"],
            "quotes": state["quotes"],
            "synthesis": state["adm_synthesis"],
        }
    )
    selected_id = decision.get("selected_provider_id") if isinstance(decision, dict) else None
    valid_ids = {q["provider_id"] for q in state["quotes"]}
    if selected_id not in valid_ids:
        logger.warning(
            "Escolha do ADM inválida; ticket continua aguardando aprovação",
            extra={"ticket_id": ticket_id, "run_id": state["run_id"]},
        )
        return {"selected_provider_id": None, "status": TicketStatus.AWAITING_ADM_APPROVAL.value}

    cancel_timeout_job(f"reminder_adm_{ticket_id}")
    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            return {"status": "error", "error": "Ticket não encontrado"}
        ticket.selected_provider_id = selected_id
        for quote in ticket.quotes:
            if quote.status == QuoteStatus.RECEIVED.value:
                quote.status = (
                    QuoteStatus.SELECTED.value
                    if quote.provider_id == selected_id
                    else QuoteStatus.REJECTED.value
                )
        _set_status(ticket, TicketStatus.PROPOSING_DATE)
        _audit(
            db,
            state["run_id"],
            ticket_id,
            "wait_for_adm",
            "adm_approved",
            {"selected_provider_id": selected_id},
        )
        db.commit()

    return {"selected_provider_id": selected_id, "status": TicketStatus.PROPOSING_DATE.value}


# -----------------------------------------------------------------------------
# Passos 3 e 4 — Data e devolutiva do prestador
# -----------------------------------------------------------------------------


async def propose_date(state: ResolverState) -> dict[str, Any]:
    """Calcula a data (Urgência × Agenda) e envia a proposta ao prestador escolhido."""
    ticket_id = state["ticket_id"]
    run_id = state["run_id"]

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            return {"status": "error", "error": "Ticket não encontrado"}

        proposal = find_optimal_schedule(
            db=db,
            property_id=state["property_id"],
            urgency=state["urgency"],
            offset_slots=state["retry_date_count"],
        )
        _set_status(ticket, TicketStatus.WAITING_DATE_CONFIRMATION)
        _audit(
            db,
            run_id,
            ticket_id,
            "propose_date",
            "provider_message_sent",
            {
                "provider_id": state["selected_provider_id"],
                "kind": "date_proposal",
                "proposed_date": proposal.proposed_date.isoformat(),
                "slot": proposal.slot_description,
            },
        )
        db.commit()

    register_date_timeout(
        ticket_id=ticket_id,
        run_id=run_id,
        timeout_minutes=DATE_TIMEOUT_MINUTES,
        callback=on_date_timeout,
    )
    return {
        "proposed_date": proposal.proposed_date.isoformat(),
        "notify_tenant": proposal.notify_tenant,
        "status": TicketStatus.WAITING_DATE_CONFIRMATION.value,
    }


async def wait_for_date(state: ResolverState) -> dict[str, Any]:
    """Espera a devolutiva do dia: aceite confirma; recusa volta ao passo 3."""
    ticket_id = state["ticket_id"]
    run_id = state["run_id"]
    reply = interrupt(
        {
            "action": "await_date_confirmation",
            "ticket_id": ticket_id,
            "proposed_date": state["proposed_date"],
        }
    )
    cancel_timeout_job(f"timeout_date_{ticket_id}")

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            return {"status": "error", "error": "Ticket não encontrado"}

        if _event(reply) == "timeout":
            return _escalate(
                db,
                ticket,
                run_id,
                "wait_for_date",
                "Prestador não respondeu à proposta de data no prazo.",
            )

        accepted = isinstance(reply, dict) and reply.get("accepted") is True
        if accepted and state["proposed_date"]:
            _set_status(ticket, TicketStatus.CONFIRMED_SCHEDULE)
            ticket.scheduled_date = datetime.fromisoformat(state["proposed_date"])
            ticket.notify_tenant = state["notify_tenant"]
            _audit(
                db,
                run_id,
                ticket_id,
                "wait_for_date",
                "date_confirmed",
                {"scheduled_date": state["proposed_date"]},
            )
            db.commit()
            return {"status": TicketStatus.CONFIRMED_SCHEDULE.value}

        attempts = state["retry_date_count"] + 1
        _audit(
            db,
            run_id,
            ticket_id,
            "wait_for_date",
            "date_refused",
            {"attempt": attempts, "proposed_date": state["proposed_date"]},
        )
        if attempts >= MAX_DATE_ATTEMPTS:
            result = _escalate(
                db,
                ticket,
                run_id,
                "wait_for_date",
                f"Prestador recusou {attempts} datas propostas.",
            )
            return {**result, "retry_date_count": attempts}

        _set_status(ticket, TicketStatus.PROPOSING_DATE)
        db.commit()
        return {"retry_date_count": attempts, "status": TicketStatus.PROPOSING_DATE.value}


# -----------------------------------------------------------------------------
# Passo 5 — Aviso ao inquilino e fechamento
# -----------------------------------------------------------------------------


async def notify_tenant_and_resolve(state: ResolverState) -> dict[str, Any]:
    """Avisa o hóspede (se houver na data), registra o aviso no imóvel e fecha o ticket."""
    ticket_id = state["ticket_id"]
    run_id = state["run_id"]

    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket:
            return {"status": "error", "error": "Ticket não encontrado"}

        if state["notify_tenant"]:
            _set_status(ticket, TicketStatus.NOTIFYING_TENANT)
            db.commit()
            resp = await generate(
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Você é o assistente virtual do imóvel. Redija uma mensagem gentil "
                            "e objetiva ao hóspede informando que um prestador fará a "
                            "manutenção agendada."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Serviço: {ticket.description}. Data/Hora: {state['proposed_date']}."
                        ),
                    },
                ],
                model="Qwen/Qwen3.5-4B",
                max_tokens=160,
                run_id=run_id,
                node="resolver_notify_tenant",
                db=db,
            )
            _audit(
                db,
                run_id,
                ticket_id,
                "notify_tenant_and_resolve",
                "tenant_notified",
                {
                    "property_id": state["property_id"],
                    "message": mask_pii(resp.content),
                    "scheduled_date": state["proposed_date"],
                },
            )

        _set_status(ticket, TicketStatus.RESOLVED)
        _audit(
            db,
            run_id,
            ticket_id,
            "notify_tenant_and_resolve",
            "ticket_resolved",
            {
                "ticket_id": ticket.id,
                "selected_provider_id": ticket.selected_provider_id,
                "scheduled_date": str(ticket.scheduled_date),
                "notify_tenant": ticket.notify_tenant,
            },
        )
        db.commit()

    return {"status": TicketStatus.RESOLVED.value, "error": None}


# -----------------------------------------------------------------------------
# Roteadores condicionais
# -----------------------------------------------------------------------------


def _is_terminal(state: ResolverState) -> bool:
    return state.get("status") in (TicketStatus.ESCALATED_TO_ADM.value, "error")


def route_after_dispatch(state: ResolverState) -> str:
    if _is_terminal(state):
        return END
    if state.get("status") == TicketStatus.NO_PROVIDERS_FALLBACK.value:
        return "wait_for_providers"
    return "request_quotes"


def route_after_wait_providers(state: ResolverState) -> str:
    return END if _is_terminal(state) else "dispatch_or_fallback"


def route_after_wait_quotes(state: ResolverState) -> str:
    return END if _is_terminal(state) else "synthesize_for_adm"


def route_after_wait_adm(state: ResolverState) -> str:
    if _is_terminal(state):
        return END
    if state.get("status") == TicketStatus.AWAITING_ADM_APPROVAL.value:
        return "wait_for_adm"
    return "propose_date"


def route_after_wait_date(state: ResolverState) -> str:
    if _is_terminal(state):
        return END
    if state.get("status") == TicketStatus.PROPOSING_DATE.value:
        return "propose_date"
    return "notify_tenant_and_resolve"


def _end_on_error(next_node: str) -> Any:
    def route(state: ResolverState) -> str:
        return END if _is_terminal(state) else next_node

    return route


# -----------------------------------------------------------------------------
# Compilação do grafo e checkpointer
# -----------------------------------------------------------------------------


def get_default_checkpointer() -> Any:
    """Checkpointer em memória: padrão em testes/SQLite e até o startup trocar pelo Postgres."""
    return MemorySaver()


# Pool do AsyncPostgresSaver (aberto no lifespan; o grafo usa só métodos assíncronos).
_checkpointer_pool: AsyncConnectionPool | None = None


async def init_resolver_checkpointer() -> None:
    """No startup com PostgreSQL, troca o grafo para AsyncPostgresSaver (estado durável).

    O PostgresSaver síncrono não implementa aget_state/ainvoke, que o Nó 3 usa.
    """
    global compiled_resolver_graph, _checkpointer_pool
    if not settings.database_url.startswith("postgresql") or settings.environment == "testing":
        return
    conninfo = settings.database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    pool = AsyncConnectionPool(
        conninfo,
        open=False,
        kwargs={"row_factory": dict_row, "autocommit": True, "prepare_threshold": 0},
    )
    try:
        await pool.open(wait=True, timeout=10)
        saver = AsyncPostgresSaver(cast(Any, pool))
        await saver.setup()
    except Exception as exc:
        await pool.close()  # sem isso o pool fica tentando reconectar em segundo plano
        logger.warning(
            "Falha ao iniciar AsyncPostgresSaver; o Nó 3 segue com MemorySaver "
            "(pausas se perdem ao reiniciar). No Windows, rode o uvicorn com "
            "--loop asyncio:SelectorEventLoop.",
            extra={"error": str(exc)},
        )
        return
    _checkpointer_pool = pool
    compiled_resolver_graph = build_resolver_graph(saver)


async def close_resolver_checkpointer() -> None:
    """Fecha o pool do checkpointer no shutdown."""
    global _checkpointer_pool
    if _checkpointer_pool is not None:
        await _checkpointer_pool.close()
        _checkpointer_pool = None


def build_resolver_graph(checkpointer: BaseCheckpointSaver | None = None) -> Any:
    """Constrói e compila o grafo de estados do Nó 3 (Resolvedor)."""
    builder = StateGraph(ResolverState)

    builder.add_node("dispatch_or_fallback", dispatch_or_fallback)
    builder.add_node("wait_for_providers", wait_for_providers)
    builder.add_node("request_quotes", request_quotes)
    builder.add_node("wait_for_quotes", wait_for_quotes)
    builder.add_node("synthesize_for_adm", synthesize_for_adm)
    builder.add_node("wait_for_adm", wait_for_adm)
    builder.add_node("propose_date", propose_date)
    builder.add_node("wait_for_date", wait_for_date)
    builder.add_node("notify_tenant_and_resolve", notify_tenant_and_resolve)

    builder.add_edge(START, "dispatch_or_fallback")
    builder.add_conditional_edges("dispatch_or_fallback", route_after_dispatch)
    builder.add_conditional_edges("wait_for_providers", route_after_wait_providers)
    builder.add_conditional_edges("request_quotes", _end_on_error("wait_for_quotes"))
    builder.add_conditional_edges("wait_for_quotes", route_after_wait_quotes)
    builder.add_conditional_edges("synthesize_for_adm", _end_on_error("wait_for_adm"))
    builder.add_conditional_edges("wait_for_adm", route_after_wait_adm)
    builder.add_conditional_edges("propose_date", _end_on_error("wait_for_date"))
    builder.add_conditional_edges("wait_for_date", route_after_wait_date)
    builder.add_edge("notify_tenant_and_resolve", END)

    saver = checkpointer or get_default_checkpointer()
    return builder.compile(checkpointer=saver)


compiled_resolver_graph = build_resolver_graph(get_default_checkpointer())


# -----------------------------------------------------------------------------
# Retomada por eventos externos (prestador, ADM, Nó S e timers)
# -----------------------------------------------------------------------------


def _thread(ticket_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": ticket_id}}


async def resume_if_waiting(
    ticket_id: str,
    waiting_node: str,
    payload: dict[str, Any],
    graph: Any | None = None,
) -> Any:
    """Retoma o grafo se ele estiver pausado em `waiting_node`; senão lança ValueError."""
    target = graph or compiled_resolver_graph
    snapshot = await target.aget_state(_thread(ticket_id))
    if not snapshot or waiting_node not in (snapshot.next or ()):
        raise ValueError(f"O chamado '{ticket_id}' não está aguardando '{waiting_node}'.")
    return await target.ainvoke(Command(resume=payload), _thread(ticket_id))


async def _resume_quietly(ticket_id: str, waiting_node: str, payload: dict[str, Any]) -> None:
    try:
        await resume_if_waiting(ticket_id, waiting_node, payload)
    except ValueError:
        logger.info(
            "Evento ignorado: chamado não está mais nessa espera",
            extra={"ticket_id": ticket_id, "waiting_node": waiting_node},
        )
    except Exception:
        logger.exception("Falha ao retomar o Nó 3", extra={"ticket_id": ticket_id})


async def on_quote_timeout(ticket_id: str, run_id: str) -> None:
    """Timer de orçamentos: segue com as respostas recebidas ou escala ao ADM."""
    await _resume_quietly(ticket_id, "wait_for_quotes", {"event": "timeout"})


async def on_date_timeout(ticket_id: str, run_id: str) -> None:
    """Timer da devolutiva do dia: escala ao ADM."""
    await _resume_quietly(ticket_id, "wait_for_date", {"event": "timeout"})


async def on_provider_collection_timeout(ticket_id: str, run_id: str) -> None:
    """Timer da coleta sob demanda: escala ao ADM."""
    await _resume_quietly(ticket_id, "wait_for_providers", {"event": "timeout"})


def on_adm_reminder(ticket_id: str, run_id: str) -> None:
    """Lembrete ao ADM: registra na trilha (a sessão do imóvel exibe o pendente)."""
    with SessionLocal() as db:
        _audit(db, run_id, ticket_id, "wait_for_adm", "adm_reminder_sent", {})
        db.commit()


async def collect_and_resume(ticket_id: str, run_id: str, category: str, city: str | None) -> None:
    """Fallback: roda a coleta do Nó S e retoma o ticket se surgir prestador validado."""
    cat = (
        ProviderCategory(category)
        if category in ProviderCategory._value2member_map_
        else ProviderCategory.GENERAL_MAINTENANCE
    )
    with SessionLocal() as db:
        try:
            await collect_on_demand(db=db, category=cat, region=city or "")
        except Exception as exc:
            logger.warning(
                "Falha na coleta sob demanda do Nó S",
                extra={"error": str(exc), "run_id": run_id, "ticket_id": ticket_id},
            )
        found = bool(_validated_providers(db, category, city))
    if found:
        await _resume_quietly(ticket_id, "wait_for_providers", {"event": "providers_ready"})


async def resume_resolution(ticket_id: str, provider_id: str, graph: Any | None = None) -> Any:
    """Retoma o grafo com a escolha do ADM."""
    return await resume_if_waiting(
        ticket_id, "wait_for_adm", {"selected_provider_id": provider_id}, graph
    )


async def record_quote_response(
    ticket_id: str,
    provider_id: str,
    amount: float,
    description: str | None,
    availability: str | None,
    graph: Any | None = None,
) -> None:
    """Registra o orçamento de um prestador; quando todos respondem, retoma o grafo.

    Texto do prestador é entrada não confiável e passa pelo guardrail
    (SecurityViolationError sobe para a API).
    """
    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket or ticket.status != TicketStatus.WAITING_QUOTES.value:
            raise ValueError(f"O chamado '{ticket_id}' não está aguardando orçamentos.")
        quote = db.execute(
            select(Quote).where(Quote.ticket_id == ticket_id, Quote.provider_id == provider_id)
        ).scalar_one_or_none()
        if quote is None or quote.status != QuoteStatus.REQUESTED.value:
            raise ValueError(f"Não há pedido de orçamento pendente para '{provider_id}'.")

        quote.amount = amount
        quote.description = (
            validate_untrusted_input(description, role="provider", run_id=ticket.run_id)
            if description
            else None
        )
        quote.proposed_availability = (
            validate_untrusted_input(availability, role="provider", run_id=ticket.run_id)
            if availability
            else None
        )
        quote.status = QuoteStatus.RECEIVED.value
        _audit(
            db,
            ticket.run_id,
            ticket_id,
            "record_quote_response",
            "quote_received",
            {"provider_id": provider_id, "amount": amount},
        )
        db.commit()
        pending = any(q.status == QuoteStatus.REQUESTED.value for q in ticket.quotes)

    if not pending:
        await resume_if_waiting(ticket_id, "wait_for_quotes", {"event": "quotes_ready"}, graph)


async def record_date_response(
    ticket_id: str,
    accepted: bool,
    message: str | None,
    graph: Any | None = None,
) -> None:
    """Registra a devolutiva do dia do prestador escolhido e retoma o grafo."""
    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket or ticket.status != TicketStatus.WAITING_DATE_CONFIRMATION.value:
            raise ValueError(f"O chamado '{ticket_id}' não está aguardando a devolutiva do dia.")
        if message:
            validate_untrusted_input(message, role="provider", run_id=ticket.run_id)
    await resume_if_waiting(ticket_id, "wait_for_date", {"accepted": accepted}, graph)


async def retry_provider_collection(ticket_id: str) -> None:
    """Dispara de novo a coleta sob demanda de um ticket em NO_PROVIDERS_FALLBACK."""
    with SessionLocal() as db:
        ticket = db.get(MaintenanceTicket, ticket_id)
        if not ticket or ticket.status != TicketStatus.NO_PROVIDERS_FALLBACK.value:
            raise ValueError(f"O chamado '{ticket_id}' não está aguardando prestadores.")
        run_id, category = ticket.run_id, ticket.category
        city = _region_of(db, ticket.property_id)
    await collect_and_resume(ticket_id, run_id, category, city)


# -----------------------------------------------------------------------------
# Implementação concreta do protocolo ResolverStarter
# -----------------------------------------------------------------------------


class LangGraphResolverStarter:
    """Implementação de ResolverStarter via LangGraph (idempotente por ticket_id)."""

    def __init__(self, graph: Any | None = None) -> None:
        self.graph = graph or compiled_resolver_graph

    async def astart_resolution(
        self,
        request: ResolutionRequest,
        db: Session | None = None,
    ) -> dict[str, Any]:
        """Inicia a resolução; se o ticket já saiu de 'open', devolve o estado atual."""
        session = db or SessionLocal()
        try:
            ticket = session.get(MaintenanceTicket, request.ticket_id)
            if not ticket:
                raise ValueError(f"Ticket '{request.ticket_id}' não encontrado.")

            if ticket.status != TicketStatus.OPEN.value:
                logger.info(
                    "Ticket já em andamento ou finalizado; execução ignorada (idempotência).",
                    extra={
                        "ticket_id": ticket.id,
                        "status": ticket.status,
                        "run_id": request.run_id,
                    },
                )
                snapshot = await self.graph.aget_state(_thread(request.ticket_id))
                return dict(snapshot.values) if snapshot and snapshot.values else {}

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
                "status": TicketStatus.OPEN.value,
                "error": None,
            }
            result = await self.graph.ainvoke(initial_state, _thread(request.ticket_id))
            # A coleta pode terminar imediatamente em modo fixture. Só a iniciamos
            # após ainvoke persistir a pausa, para não perder o evento providers_ready.
            if isinstance(result, dict) and result.get("status") == (
                TicketStatus.NO_PROVIDERS_FALLBACK.value
            ):
                _spawn(
                    collect_and_resume(
                        ticket.id,
                        request.run_id,
                        ticket.category,
                        _region_of(session, ticket.property_id),
                    )
                )
            return dict(result) if isinstance(result, dict) else {}
        finally:
            if db is None:
                session.close()

    def start_resolution(self, request: ResolutionRequest) -> None:
        """Versão síncrona exigida pelo protocolo ResolverStarter."""
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self.astart_resolution(request))
            return
        _spawn(self.astart_resolution(request))


if TYPE_CHECKING:
    # Garante no `mypy app` que a implementação segue o contrato Nó 2 -> Nó 3.
    _resolver_contract: ResolverStarter = LangGraphResolverStarter()
