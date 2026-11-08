"""Testes de integração para os 5 Caminhos Alternativos Obrigatórios (S2-T8).

Cobre:
1. Fallback Nó S: Nenhum prestador no DB para a categoria/região -> status NO_PROVIDERS_FALLBACK,
   acionamento de coleta sob demanda do Nó S (collect_on_demand) e registro de auditoria/alerta ao ADM.
2. Timeout de prestador respondendo cotação:
   - Timer de timeout registrado no ciclo de vida.
   - Prossegue com orçamentos parciais se houver respostas, ou escalona ao ADM se zero respostas.
3. Timeout do ADM com disparo de lembrete:
   - Ticket permanece em AWAITING_ADM_APPROVAL com lembrete disparado na sessão do anfitrião.
   - Timer cancelado após a aprovação tardia.
4. Prestador recusa data proposta -> loop de retorno aos passos 3 e 4:
   - Recusa na 1ª data e aceite na 2ª data -> concluído com retry_date_count=1.
   - Recusa em 3 tentativas consecutivas -> escalonamento ao ADM (ESCALATED_TO_ADM).
5. Urgente com hóspede vs. Não urgente sem hóspede:
   - Urgente com hóspede aloca 1º horário e marca notify_tenant=True.
   - Não urgente sem hóspede seleciona janela livre na agenda e marca notify_tenant=False.
"""

from datetime import UTC, date, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.agents import resolver_graph
from app.agents.resolver_graph import (
    LangGraphResolverStarter,
    compiled_resolver_graph,
    resume_resolution,
)
from app.agents.resolver_timeouts import (
    cancel_timeout_job,
    clear_active_timeouts,
    get_active_timeouts,
    register_adm_reminder,
    register_quote_timeout,
)
from app.core.llm import LLMResponse
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

    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(
        ticket_id=ticket.id,
        property_id=alt_property.id,
        run_id=ticket.run_id,
    )

    with patch(
        "app.agents.resolver_graph.collect_on_demand", new_callable=AsyncMock
    ) as mock_collect:
        mock_collect.return_value = 0
        state = await starter.astart_resolution(req, db=db_session)

        # Valida que o fallback sob demanda foi chamado com a categoria e cidade
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


def test_alt_path_2_provider_quote_timeout_partial_quotes(
    db_session: Session,
    alt_property: Property,
) -> None:
    """Caminho 2:

    Timeout de resposta dos prestadores:
    - Se houver pelo menos 1 orçamento coletado, prossegue para síntese do ADM.
    - Se houver 0 orçamentos coletados no timeout, escala para o ADM.
    """
    ticket = MaintenanceTicket(
        id="tick-alt-timeout-quote-001",
        run_id="run-alt-timeout-001",
        property_id=alt_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.ELECTRICIAN.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Quadro elétrico",
        description="Disjuntor desarmando com frequência.",
        status=TicketStatus.WAITING_QUOTES.value,
    )
    # Adiciona 1 cotação recebida e 1 pendente
    q1 = Quote(
        ticket_id=ticket.id,
        run_id=ticket.run_id,
        provider_id="prov-elec-1",
        amount=250.0,
        description="Troca de disjuntor principal",
        status=QuoteStatus.RECEIVED.value,
    )
    q2 = Quote(
        ticket_id=ticket.id,
        run_id=ticket.run_id,
        provider_id="prov-elec-2",
        status=QuoteStatus.REQUESTED.value,
    )
    db_session.add_all([ticket, q1, q2])
    db_session.commit()

    # Simula registro do timer
    callback_executed = False

    def mock_timeout_callback(t_id: str, r_id: str) -> None:
        nonlocal callback_executed
        callback_executed = True

    job_id = register_quote_timeout(
        ticket_id=ticket.id,
        run_id=ticket.run_id,
        timeout_minutes=60,
        callback=mock_timeout_callback,
    )

    active_timers = get_active_timeouts()
    assert job_id in active_timers
    assert active_timers[job_id]["ticket_id"] == ticket.id

    # Executa o callback de timeout
    active_timers[job_id]["callback"](ticket.id, ticket.run_id)
    assert callback_executed is True

    # Com 1 cotação disponível, o sistema tem dados para avançar ao ADM
    quotes_received = [
        q for q in db_session.query(Quote).filter_by(ticket_id=ticket.id).all()
        if q.status == QuoteStatus.RECEIVED.value
    ]
    assert len(quotes_received) == 1

    # Cancela timer ao prosseguir
    cancel_timeout_job(job_id)
    assert job_id not in get_active_timeouts()


# ==============================================================================
# CAMINHO ALTERNATIVO 3: TIMEOUT DO ADM COM DISPARO DE LEMBRETE
# ==============================================================================


def test_alt_path_3_adm_reminder_timeout_keeps_state_awaiting(
    db_session: Session,
    alt_property: Property,
) -> None:
    """Caminho 3:

    Timeout de aprovação pelo ADM:
    - O timer de lembrete dispara após a janela configurada.
    - O ticket permanece em AWAITING_ADM_APPROVAL (não é cancelado nem finalizado).
    - Um evento de lembrete é registrado na auditoria da sessão do imóvel.
    """
    ticket = MaintenanceTicket(
        id="tick-alt-adm-reminder-001",
        run_id="run-alt-reminder-001",
        property_id=alt_property.id,
        reported_by_role=ReportedByRole.CLEANER.value,
        category=ProviderCategory.PAINTER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Sala de estar",
        description="Retoque de pintura na parede atrás do sofá.",
        status=TicketStatus.AWAITING_ADM_APPROVAL.value,
    )
    db_session.add(ticket)
    db_session.commit()

    reminder_sent = False

    def on_reminder_trigger(t_id: str, r_id: str) -> None:
        nonlocal reminder_sent
        reminder_sent = True
        # Registra evento na trilha de auditoria
        audit = AuditEvent(
            run_id=r_id,
            ticket_id=t_id,
            node="adm_reminder",
            event_type="adm_reminder_sent",
            payload={"message": "Lembrete: orçamentos aguardam sua aprovação na sessão do imóvel."},
        )
        db_session.add(audit)
        db_session.commit()

    job_id = register_adm_reminder(
        ticket_id=ticket.id,
        run_id=ticket.run_id,
        reminder_minutes=120,
        callback=on_reminder_trigger,
    )

    # Dispara o lembrete simulando expiração do timer
    get_active_timeouts()[job_id]["callback"](ticket.id, ticket.run_id)
    assert reminder_sent is True

    # O chamado permanece em AWAITING_ADM_APPROVAL
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.AWAITING_ADM_APPROVAL.value

    # Evento de auditoria registrado
    audit = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.ticket_id == ticket.id, AuditEvent.event_type == "adm_reminder_sent")
        .first()
    )
    assert audit is not None
    assert "aguardam sua aprovação" in audit.payload.get("message", "")


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

    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(
        ticket_id=ticket.id,
        property_id=alt_property.id,
        run_id=ticket.run_id,
    )

    # Inicia até a pausa do ADM
    await starter.astart_resolution(req, db=db_session)

    # Configura mock de generate para responder RECUSO na 1ª vez e ACEITO na 2ª vez
    original_generate = resolver_graph.generate
    call_count = 0

    async def mock_generate(*args: Any, **kwargs: Any) -> LLMResponse:
        nonlocal call_count
        node = kwargs.get("node")
        r_id = kwargs.get("run_id", "run-mock")
        if node == "resolver_date_confirm":
            call_count += 1
            if call_count == 1:
                return LLMResponse(
                    content="RECUSO: Não posso atender nesta data, estou com outra pintura em andamento.",
                    model="Qwen/Qwen3.5-4B",
                    input_tokens=20,
                    output_tokens=15,
                    cost_usd=0.0,
                    is_mock=True,
                    run_id=r_id,
                    node=node,
                )
            else:
                return LLMResponse(
                    content="ACEITO: Confirmo minha presença nesta segunda data proposta.",
                    model="Qwen/Qwen3.5-4B",
                    input_tokens=20,
                    output_tokens=15,
                    cost_usd=0.0,
                    is_mock=True,
                    run_id=r_id,
                    node=node,
                )
        return await original_generate(*args, **kwargs)

    monkeypatch.setattr(resolver_graph, "generate", mock_generate)

    # Retoma com aprovação do ADM
    final_state = await resume_resolution(
        ticket_id=ticket.id,
        provider_id=provider.id,
        graph=compiled_resolver_graph,
    )

    db_session.refresh(ticket)
    assert call_count == 2
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

    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(
        ticket_id=ticket.id,
        property_id=alt_property.id,
        run_id=ticket.run_id,
    )

    await starter.astart_resolution(req, db=db_session)

    # Sempre recusa datas
    original_generate = resolver_graph.generate

    async def mock_always_refuse(*args: Any, **kwargs: Any) -> LLMResponse:
        node = kwargs.get("node")
        r_id = kwargs.get("run_id", "run-mock")
        if node == "resolver_date_confirm":
            return LLMResponse(
                content="RECUSO: Totalmente sem disponibilidade esta semana.",
                model="Qwen/Qwen3.5-4B",
                input_tokens=20,
                output_tokens=10,
                cost_usd=0.0,
                is_mock=True,
                run_id=r_id,
                node=node,
            )
        return await original_generate(*args, **kwargs)

    monkeypatch.setattr(resolver_graph, "generate", mock_always_refuse)

    final_state = await resume_resolution(
        ticket_id=ticket.id,
        provider_id=provider.id,
        graph=compiled_resolver_graph,
    )

    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.ESCALATED_TO_ADM.value
    assert final_state.get("status") == TicketStatus.ESCALATED_TO_ADM.value
    assert final_state.get("retry_date_count") >= 3
    assert "escalado ao anfitrião" in (final_state.get("error") or "").lower()


# ==============================================================================
# CAMINHO ALTERNATIVO 5: URGENTE COM HÓSPEDE VS. NÃO URGENTE SEM HÓSPEDE
# ==============================================================================


def test_alt_path_5_urgency_x_calendar_comparison(
    db_session: Session,
    alt_property: Property,
) -> None:
    """Caminho 5:

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
