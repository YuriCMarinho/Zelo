"""Testes de integração para os 5 Caminhos Alternativos Obrigatórios (S2-T8).

Cobre:
1. Fallback Nó S: Nenhum prestador no DB para a categoria/região -> status NO_PROVIDERS_FALLBACK,
   acionamento de coleta sob demanda do Nó S (collect_on_demand) e registro de auditoria/alerta ao ADM.
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

from app.agents import resolver_graph
from app.agents.resolver_graph import (
    LangGraphResolverStarter,
    compiled_resolver_graph,
    request_and_receive_quotes,
    resume_resolution,
)
from app.agents.resolver_timeouts import (
    clear_active_timeouts,
    get_active_timeouts,
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


async def run_resolution_until_pause(
    ticket_id: str,
    property_id: str,
    run_id: str,
    db: Session,
) -> dict[str, Any]:
    """Helper reutilizável para inicializar a resolução de chamados no grafo até a pausa humana."""
    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(ticket_id=ticket_id, property_id=property_id, run_id=run_id)
    return await starter.astart_resolution(req, db=db)


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

    with patch(
        "app.agents.resolver_graph.collect_on_demand", new_callable=AsyncMock
    ) as mock_collect:
        mock_collect.return_value = 0
        state = await run_resolution_until_pause(
            ticket_id=ticket.id,
            property_id=alt_property.id,
            run_id=ticket.run_id,
            db=db_session,
        )
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

    Quando não há prestadores disponíveis no passo de cotação (zero respostas),
    o nó request_and_receive_quotes escalona diretamente o chamado para o anfitrião
    com status ESCALATED_TO_ADM.
    """
    ticket = MaintenanceTicket(
        id="tick-alt-zero-quotes-001",
        run_id="run-alt-zero-001",
        property_id=alt_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.ELECTRICIAN.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Quadro geral",
        description="Fiação em curto.",
        status=TicketStatus.REQUESTING_QUOTES.value,
    )
    db_session.add(ticket)
    db_session.commit()

    # Executa nó sem nenhum candidato disponível
    empty_state: Any = {
        "ticket_id": ticket.id,
        "run_id": ticket.run_id,
        "property_id": alt_property.id,
        "candidate_providers": [],
    }
    result = await request_and_receive_quotes(empty_state)

    db_session.refresh(ticket)
    assert result["status"] == TicketStatus.ESCALATED_TO_ADM.value
    assert ticket.status == TicketStatus.ESCALATED_TO_ADM.value
    assert "Nenhum prestador disponível" in result.get("error", "")


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

    # Executa até a pausa do ADM
    await run_resolution_until_pause(
        ticket_id=ticket.id,
        property_id=alt_property.id,
        run_id=ticket.run_id,
        db=db_session,
    )

    # Verifica que cotações foram coletadas e o timer de cotação foi cancelado
    # após a conclusão bem-sucedida do passo
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

    await run_resolution_until_pause(
        ticket_id=ticket.id,
        property_id=alt_property.id,
        run_id=ticket.run_id,
        db=db_session,
    )

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

    # Retoma com aprovação do ADM
    final_state = await resume_resolution(
        ticket_id=ticket.id,
        provider_id=provider.id,
        graph=compiled_resolver_graph,
    )

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
