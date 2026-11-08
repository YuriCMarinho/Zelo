"""Testes de integração para os 5 Caminhos Alternativos Obrigatórios (S2-T8).

Cobre:
1. Fallback Nó S: nenhum prestador no DB para a categoria/região -> NO_PROVIDERS_FALLBACK,
   coleta sob demanda do Nó S em segundo plano e auditoria/alerta ao ADM.
2. Timeout de prestador respondendo cotação:
   - Timer de timeout registrado no ciclo de vida nativo do grafo.
   - Zero prestadores/orçamentos escalona ao ADM (ESCALATED_TO_ADM).
   - Prossegue com orçamentos parciais disponíveis.
3. Timeout do ADM com disparo de lembrete:
   - Grafo registra lembrete nativo via register_adm_reminder no Passo 2.
   - Ticket permanece em AWAITING_ADM_APPROVAL com lembrete disparado.
   - Timer cancelado automaticamente após aprovação do ADM em resume_resolution.
4. Prestador recusa data proposta -> loop de retorno aos passos 3 e 4:
   - Recusa na 1ª data e aceite na 2ª data -> concluído com retry_date_count=1.
   - Recusa em 3 tentativas consecutivas -> escalonamento ao ADM (ESCALATED_TO_ADM).
5. Urgente com hóspede vs. Não urgente sem hóspede (e fluxo E2E para imóvel desocupado):
   - Urgente com hóspede aloca 1º horário e marca notify_tenant=True.
   - Não urgente sem hóspede seleciona janela livre na agenda e marca notify_tenant=False.
   - Grafo E2E em imóvel vazio pula etapa de notificação ao inquilino.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agents.resolver_graph import (
    LangGraphResolverStarter,
    compiled_resolver_graph,
    on_quote_timeout,
    record_date_response,
    record_quote_response,
    resume_resolution,
)
from app.agents.resolver_timeouts import (
    clear_active_timeouts,
    get_active_timeouts,
)
from app.db.models import AuditEvent, Booking, MaintenanceTicket, Property, Provider, Quote
from app.schemas.common import (
    ProviderCategory,
    QuoteStatus,
    ReportedByRole,
    TicketStatus,
    TicketUrgency,
)
from app.schemas.resolver import ResolutionRequest
from app.services.scheduling import find_optimal_schedule


@pytest.fixture(autouse=True)
def clean_timeouts() -> None:
    """Garante isolamento de timers entre execuções de testes."""
    clear_active_timeouts()


@pytest.fixture
def alt_property(db_session: Session) -> Property:
    """Cria um imóvel de teste para os caminhos alternativos."""
    prop = Property(
        id="prop-alt-001",
        name="Flat Jardins Design",
        description="Flat confortável em São Paulo com automação residencial.",
        address="Alameda Santos, 1200",
        city="São Paulo",
        state="SP",
        rules_faq="Check-in 14h, check-out 11h. Silêncio após 22h.",
    )
    db_session.add(prop)
    db_session.commit()
    return prop


async def run_resolution_until_pause(
    ticket_id: str,
    property_id: str,
    run_id: str,
    db: Session,
) -> dict[str, Any]:
    """Inicia a resolução e, se houver pedidos de orçamento, responde por todos os prestadores.

    O Nó 3 não inventa orçamentos: ele pausa até cada prestador responder. Este helper
    simula as respostas (canal simulado) para levar o chamado até a decisão do ADM.
    """
    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(ticket_id=ticket_id, run_id=run_id)
    state = await starter.astart_resolution(req, db=db)
    await answer_all_quotes(db, ticket_id)
    return state


async def answer_all_quotes(db: Session, ticket_id: str) -> None:
    """Cada prestador consultado envia seu orçamento pelo canal (endpoint/simulador)."""
    pending = (
        db.query(Quote)
        .filter(Quote.ticket_id == ticket_id, Quote.status == QuoteStatus.REQUESTED.value)
        .all()
    )
    for idx, quote in enumerate(pending):
        await record_quote_response(
            ticket_id=ticket_id,
            provider_id=quote.provider_id,
            amount=200.0 + idx * 40,
            description="Serviço completo com garantia",
            availability="Esta semana",
        )
    db.expire_all()


# ==============================================================================
# CAMINHO ALTERNATIVO 1: NENHUM PRESTADOR NO DB (FALLBACK NÓ S + ALERTA ADM)
# ==============================================================================


@pytest.mark.asyncio
async def test_alt_path_1_no_providers_triggers_node_s_fallback(
    db_session: Session,
    alt_property: Property,
) -> None:
    """Caminho 1:

    Quando não há nenhum prestador validado para a categoria solicitada no banco:
    1. O grafo detecta candidate_providers vazio.
    2. O status do ticket é atualizado para NO_PROVIDERS_FALLBACK.
    3. collect_on_demand é acionado assincronamente para busca sob demanda.
    4. Um evento de auditoria informando o ADM é persistido.
    """
    # Imóvel sem nenhum prestador da categoria ORGANIZER
    ticket = MaintenanceTicket(
        id="tick-alt-no-prov-001",
        run_id="run-alt-no-prov-001",
        property_id=alt_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.ORGANIZER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Armário",
        description="Porta do guarda-roupas emperrada e desencaixada.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    spawned: list[Any] = []
    with (
        patch("app.agents.resolver_graph._spawn", spawned.append),
        patch(
            "app.agents.resolver_graph.collect_on_demand", new_callable=AsyncMock
        ) as mock_collect,
    ):
        mock_collect.return_value = 0
        state = await run_resolution_until_pause(
            ticket_id=ticket.id,
            property_id=alt_property.id,
            run_id=ticket.run_id,
            db=db_session,
        )
        # A coleta do Nó S roda em segundo plano, sem bloquear o grafo
        assert len(spawned) == 1
        await spawned[0]
        mock_collect.assert_awaited_once()

    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.NO_PROVIDERS_FALLBACK.value
    assert state.get("status") == TicketStatus.NO_PROVIDERS_FALLBACK.value
    assert len(state.get("candidate_providers", [])) == 0

    # Verifica o registro de auditoria notificando o ADM
    audit = (
        db_session.query(AuditEvent)
        .filter(
            AuditEvent.ticket_id == ticket.id,
            AuditEvent.event_type == "no_providers_fallback",
        )
        .first()
    )
    assert audit is not None
    assert audit.payload.get("notified_adm") is True
    assert audit.payload.get("category") == ProviderCategory.ORGANIZER.value


def test_alt_path_1_via_http_chat(
    client: TestClient,
    db_session: Session,
    alt_property: Property,
) -> None:
    """Caminho 1 via API HTTP:

    POST /api/chat para categoria sem prestadores (ex: encanador) resulta em chamado
    aberto e imediatamente colocado com status NO_PROVIDERS_FALLBACK pelo Nó 3.
    """
    chat_payload = {
        "property_id": alt_property.id,
        "message": "O cano da pia da cozinha está quebrado e vazando água no chão.",
        "sender_role": ReportedByRole.TENANT.value,
        "run_id": "run-alt-chat-plumber",
    }
    response = client.post("/api/chat", json=chat_payload)
    assert response.status_code == 200
    data = response.json()

    assert data["route_destination"] == "maintenance_node2"
    ticket_id = data["ticket_id"]
    assert ticket_id is not None

    ticket_resp = client.get(f"/api/tickets/{ticket_id}")
    assert ticket_resp.status_code == 200
    ticket_data = ticket_resp.json()
    assert ticket_data["status"] == TicketStatus.NO_PROVIDERS_FALLBACK.value


# ==============================================================================
# CAMINHO ALTERNATIVO 2: TIMEOUT DE PRESTADOR RESPONDENDO COTAÇÃO
# ==============================================================================


@pytest.mark.asyncio
async def test_alt_path_2_zero_providers_escalates_to_adm(
    db_session: Session,
    alt_property: Property,
) -> None:
    """Caminho 2 (Cenário A - Zero Respostas):

    Os prestadores foram consultados mas nenhum respondeu até o timeout de cotação:
    o chamado é escalado ao anfitrião (ESCALATED_TO_ADM) e os pedidos viram TIMEOUT.
    """
    db_session.add(
        Provider(
            id="prov-elec-alt-silent",
            name="Elétrica Silenciosa",
            category=ProviderCategory.ELECTRICIAN.value,
            region="São Paulo",
            phone="+55 11 98888-7777",
            is_validated=True,
            rating=4.1,
        )
    )
    ticket = MaintenanceTicket(
        id="tick-alt-zero-quotes-001",
        run_id="run-alt-zero-001",
        property_id=alt_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.ELECTRICIAN.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Quadro geral",
        description="Fiação em curto.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    starter = LangGraphResolverStarter(compiled_resolver_graph)
    await starter.astart_resolution(
        ResolutionRequest(ticket_id=ticket.id, run_id=ticket.run_id), db=db_session
    )
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.WAITING_QUOTES.value

    await on_quote_timeout(ticket.id, ticket.run_id)

    db_session.expire_all()
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.ESCALATED_TO_ADM.value
    quotes = db_session.query(Quote).filter_by(ticket_id=ticket.id).all()
    assert quotes and all(q.status == QuoteStatus.TIMEOUT.value for q in quotes)


@pytest.mark.asyncio
async def test_alt_path_2_quote_timeout_lifecycle_and_callback(
    db_session: Session,
    alt_property: Property,
) -> None:
    """Caminho 2 (Cenário B - Ciclo de Vida Nativo de Timeout):

    Verifica o registro e disparo do timer nativo de timeout de cotação
    e o cancelamento automático quando os orçamentos são concluídos.
    """
    provider = Provider(
        id="prov-elec-alt-timeout",
        name="Elétrica Express",
        category=ProviderCategory.ELECTRICIAN.value,
        region="São Paulo",
        phone="+55 11 98888-3333",
        is_validated=True,
        rating=4.8,
    )
    db_session.add(provider)

    ticket = MaintenanceTicket(
        id="tick-alt-quote-timer-001",
        run_id="run-alt-quote-timer-001",
        property_id=alt_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.ELECTRICIAN.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Quadro elétrico",
        description="Disjuntor desarmando.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    # O Nó 3 pede o orçamento e registra o timer de cotação enquanto espera
    starter = LangGraphResolverStarter(compiled_resolver_graph)
    await starter.astart_resolution(
        ResolutionRequest(ticket_id=ticket.id, run_id=ticket.run_id), db=db_session
    )
    assert f"timeout_quote_{ticket.id}" in get_active_timeouts()

    # Quando o prestador responde, o timer é cancelado
    await answer_all_quotes(db_session, ticket.id)
    assert f"timeout_quote_{ticket.id}" not in get_active_timeouts()

    # O chamado prosseguiu para a síntese do ADM com os orçamentos recebidos
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.AWAITING_ADM_APPROVAL.value
    quotes = db_session.query(Quote).filter_by(ticket_id=ticket.id).all()
    assert len(quotes) >= 1


# ==============================================================================
# CAMINHO ALTERNATIVO 3: TIMEOUT DO ADM COM DISPARO DE LEMBRETE NATIVO
# ==============================================================================


@pytest.mark.asyncio
async def test_alt_path_3_adm_reminder_native_timeout_flow(
    db_session: Session,
    alt_property: Property,
) -> None:
    """Caminho 3:

    Timeout de aprovação pelo ADM:
    - O grafo entra em AWAITING_ADM_APPROVAL e registra o timer nativo reminder_adm_{ticket_id}.
    - O callback nativo é exercitado sem alterar o status de aprovação.
    - Após o anfitrião aprovar via resume_resolution, o timer é cancelado automaticamente.
    """
    provider = Provider(
        id="prov-paint-adm-rem",
        name="Pinturas Santos",
        category=ProviderCategory.PAINTER.value,
        region="São Paulo",
        phone="+55 11 98888-4444",
        is_validated=True,
        rating=4.9,
    )
    db_session.add(provider)

    ticket = MaintenanceTicket(
        id="tick-alt-adm-rem-001",
        run_id="run-alt-rem-001",
        property_id=alt_property.id,
        reported_by_role=ReportedByRole.CLEANER.value,
        category=ProviderCategory.PAINTER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Sala",
        description="Pintura danificada no corredor.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    # Inicia até a pausa humana do ADM
    await run_resolution_until_pause(
        ticket_id=ticket.id,
        property_id=alt_property.id,
        run_id=ticket.run_id,
        db=db_session,
    )

    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.AWAITING_ADM_APPROVAL.value

    # Timer nativo deve estar registrado no APScheduler/registro em memória
    job_id = f"reminder_adm_{ticket.id}"
    active_timers = get_active_timeouts()
    assert job_id in active_timers

    # Dispara o callback nativo registrado pela aplicação
    native_callback = active_timers[job_id]["callback"]
    native_callback(ticket.id, ticket.run_id)

    # O chamado permanece em AWAITING_ADM_APPROVAL
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.AWAITING_ADM_APPROVAL.value

    # Quando o ADM aprova tardiamente, o timer é cancelado pelo grafo
    await resume_resolution(
        ticket_id=ticket.id,
        provider_id=provider.id,
        graph=compiled_resolver_graph,
    )

    assert job_id not in get_active_timeouts()
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.WAITING_DATE_CONFIRMATION.value

    await record_date_response(ticket.id, accepted=True, message="Confirmo.")
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.RESOLVED.value


# ==============================================================================
# CAMINHO ALTERNATIVO 4: PRESTADOR RECUSA DATA -> LOOP DE RETORNO (PASSOS 3 E 4)
# ==============================================================================


@pytest.mark.asyncio
async def test_alt_path_4_provider_refuses_date_retries_and_succeeds(
    db_session: Session,
    alt_property: Property,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caminho 4 (Cenário A):

    Prestador recusa a primeira data proposta.
    O grafo incrementa retry_date_count, retorna ao Passo 3/4, propõe a próxima data.
    Na 2ª tentativa o prestador aceita, e o chamado conclui como RESOLVED.
    """
    provider = Provider(
        id="prov-painter-alt-1",
        name="Pinturas Express",
        category=ProviderCategory.PAINTER.value,
        region="São Paulo",
        phone="+55 11 98888-0001",
        is_validated=True,
        rating=4.9,
    )
    db_session.add(provider)

    ticket = MaintenanceTicket(
        id="tick-alt-refuse-date-001",
        run_id="run-alt-refuse-001",
        property_id=alt_property.id,
        reported_by_role=ReportedByRole.CLEANER.value,
        category=ProviderCategory.PAINTER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Corredor",
        description="Pintura descascando perto da entrada.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    # Inicia até a pausa do ADM
    await run_resolution_until_pause(
        ticket_id=ticket.id,
        property_id=alt_property.id,
        run_id=ticket.run_id,
        db=db_session,
    )

    await resume_resolution(
        ticket_id=ticket.id,
        provider_id=provider.id,
        graph=compiled_resolver_graph,
    )

    # Prestador recusa a 1ª data e aceita a 2ª (devolutiva do dia real)
    await record_date_response(ticket.id, accepted=False, message="Estou com outra obra.")
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.WAITING_DATE_CONFIRMATION.value
    await record_date_response(ticket.id, accepted=True, message="Confirmo a nova data.")

    final_state = compiled_resolver_graph.get_state(
        {"configurable": {"thread_id": ticket.id}}
    ).values
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.RESOLVED.value
    assert final_state.get("status") == TicketStatus.RESOLVED.value
    assert final_state.get("retry_date_count") == 1
    assert ticket.scheduled_date is not None


@pytest.mark.asyncio
async def test_alt_path_4_provider_refuses_3_times_escalates_to_adm(
    db_session: Session,
    alt_property: Property,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Caminho 4 (Cenário B):

    Prestador recusa 3 datas consecutivas.
    O grafo atinge o limite de 3 tentativas e escala o chamado para o anfitrião
    com status ESCALATED_TO_ADM.
    """
    provider = Provider(
        id="prov-elec-alt-refuse",
        name="Eletro Santos",
        category=ProviderCategory.ELECTRICIAN.value,
        region="São Paulo",
        phone="+55 11 98888-0002",
        is_validated=True,
        rating=4.7,
    )
    db_session.add(provider)

    ticket = MaintenanceTicket(
        id="tick-alt-escalate-001",
        run_id="run-alt-escalate-001",
        property_id=alt_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.ELECTRICIAN.value,
        urgency=TicketUrgency.URGENT.value,
        location_in_property="Cozinha",
        description="Tomadas em curto sem energia.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    await run_resolution_until_pause(
        ticket_id=ticket.id,
        property_id=alt_property.id,
        run_id=ticket.run_id,
        db=db_session,
    )

    await resume_resolution(
        ticket_id=ticket.id,
        provider_id=provider.id,
        graph=compiled_resolver_graph,
    )
    for _ in range(3):
        await record_date_response(ticket.id, accepted=False, message="Sem disponibilidade.")

    final_state = compiled_resolver_graph.get_state(
        {"configurable": {"thread_id": ticket.id}}
    ).values
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.ESCALATED_TO_ADM.value
    assert final_state.get("status") == TicketStatus.ESCALATED_TO_ADM.value
    assert final_state.get("retry_date_count") >= 3
    assert "recusou 3 datas" in (final_state.get("error") or "").lower()


# ==============================================================================
# CAMINHO ALTERNATIVO 5: URGENTE COM HÓSPEDE VS. NÃO URGENTE SEM HÓSPEDE
# ==============================================================================


def test_alt_path_5_urgency_x_calendar_comparison(
    db_session: Session,
    alt_property: Property,
) -> None:
    """Caminho 5 (Regra Determinística):

    Regra determinística Urgência × Agenda:
    - Cenário A: Chamado URGENT com hóspede presente:
      Deve alocar imediatamente o primeiro horário emergencial e marcar notify_tenant=True.
    - Cenário B: Chamado LOW/NORMAL sem hóspede na janela:
      Deve selecionar uma janela sem hóspede e marcar notify_tenant=False.
    """
    today = date.today()

    # Cria reserva ocupando de hoje até hoje+3
    active_booking = Booking(
        id="book-alt-active-guest",
        property_id=alt_property.id,
        guest_name="Rodrigo Turista",
        guest_contact="+55 11 99999-8888",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=3),
    )
    # Reserva futura começando daqui a 6 dias (deixa janela livre entre today+3 e today+6)
    future_booking = Booking(
        id="book-alt-future-guest",
        property_id=alt_property.id,
        guest_name="Fernanda Viagens",
        guest_contact="+55 11 99999-7777",
        start_date=today + timedelta(days=6),
        end_date=today + timedelta(days=10),
    )
    db_session.add_all([active_booking, future_booking])
    db_session.commit()

    # --- Cenário A: Chamado Urgente com Hóspede Presente ---
    urgent_proposal = find_optimal_schedule(
        db=db_session,
        property_id=alt_property.id,
        urgency=TicketUrgency.URGENT.value,
    )
    assert urgent_proposal.notify_tenant is True
    assert urgent_proposal.has_guest is True
    assert urgent_proposal.proposed_date > datetime.now(UTC)
    assert "Horário emergencial" in urgent_proposal.slot_description

    # --- Cenário B: Chamado Não Urgente (janela sem hóspede) ---
    normal_proposal = find_optimal_schedule(
        db=db_session,
        property_id=alt_property.id,
        urgency=TicketUrgency.NORMAL.value,
    )
    assert normal_proposal.notify_tenant is False
    assert normal_proposal.has_guest is False
    # A data proposta deve cair entre o fim da primeira reserva e início da segunda
    assert normal_proposal.proposed_date.date() >= (today + timedelta(days=3))
    assert normal_proposal.proposed_date.date() < (today + timedelta(days=6))
    assert "sem reserva ativa" in normal_proposal.slot_description.lower()


@pytest.mark.asyncio
async def test_alt_path_5_empty_property_skips_tenant_notification_e2e(
    db_session: Session,
    alt_property: Property,
) -> None:
    """Caminho 5 (Integração E2E - Imóvel Desocupado no Passo 5):

    Garante que para chamados em imóvel vazio:
    - O agendamento ocorre em janela sem hóspede.
    - O Passo 5 (notify_tenant_and_resolve) identifica notify_tenant=False.
    - O chamado avança diretamente para RESOLVED sem emitir notificação a inquilino.
    """
    # Imóvel sem nenhuma reserva (vazio)
    provider = Provider(
        id="prov-organizer-empty-prop",
        name="Organizadora SP",
        category=ProviderCategory.ORGANIZER.value,
        region="São Paulo",
        phone="+55 11 99999-5555",
        is_validated=True,
        rating=4.9,
    )
    db_session.add(provider)

    ticket = MaintenanceTicket(
        id="tick-alt-empty-prop-001",
        run_id="run-alt-empty-001",
        property_id=alt_property.id,
        reported_by_role=ReportedByRole.CLEANER.value,
        category=ProviderCategory.ORGANIZER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Armário suíte",
        description="Ajuste de prateleiras soltas.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    # Inicia até a pausa do ADM
    await run_resolution_until_pause(
        ticket_id=ticket.id,
        property_id=alt_property.id,
        run_id=ticket.run_id,
        db=db_session,
    )

    # Retoma com aprovação do ADM e confirma a data com o prestador
    await resume_resolution(
        ticket_id=ticket.id,
        provider_id=provider.id,
        graph=compiled_resolver_graph,
    )
    await record_date_response(ticket.id, accepted=True, message=None)
    final_state = compiled_resolver_graph.get_state(
        {"configurable": {"thread_id": ticket.id}}
    ).values

    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.RESOLVED.value
    # Imóvel vazio não necessita de notificação de inquilino
    assert ticket.notify_tenant is False
    assert final_state.get("notify_tenant") is False
    assert ticket.scheduled_date is not None

    # Verifica que não foi gravada auditoria de inquilino notificado
    tenant_audit = (
        db_session.query(AuditEvent)
        .filter(
            AuditEvent.ticket_id == ticket.id,
            AuditEvent.event_type == "tenant_notified",
        )
        .first()
    )
    assert tenant_audit is None
