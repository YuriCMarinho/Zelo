"""Testes unitários e de integração para o Nó 3: Agente Resolvedor em LangGraph (S2-T6).

Cobre:
1. Regra determinística Urgência × Agenda (app.services.scheduling).
2. Gerenciador de timeouts e lembretes (app.agents.resolver_timeouts).
3. Máquina de estados LangGraph de 5 passos com interrupção para decisão do ADM e retomada.
4. Caminhos alternativos: fallback por ausência de prestadores, loop de recusa de data,
   escalonamento após 3 recusas, e idempotência do ResolverStarter.
5. Endpoints HTTP da API de Tickets (/api/tickets e /api/properties/{id}/tickets).
"""

from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

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
from app.db.models import Booking, MaintenanceTicket, Property, Provider, Quote
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
def setup_sessions(monkeypatch: pytest.MonkeyPatch, db_session: Session) -> None:
    """Garante que todos os nós do grafo usem o engine do SQLite in-memory de teste."""
    session_factory = sessionmaker(
        autocommit=False, autoflush=False, bind=db_session.get_bind()
    )
    monkeypatch.setattr(resolver_graph, "SessionLocal", session_factory)


@pytest.fixture
def sample_property(db_session: Session) -> Property:
    """Cria um imóvel padrão para os testes do resolvedor."""
    prop = Property(
        id="prop-resolver-001",
        name="Cobertura Copacabana Mar",
        description="Amplo apartamento de frente para o mar.",
        address="Avenida Atlântica, 1500",
        city="Rio de Janeiro",
        state="RJ",
        rules_faq="Check-in às 14h, check-out às 11h. Silêncio após 22h.",
    )
    db_session.add(prop)
    db_session.commit()
    return prop


@pytest.fixture
def sample_providers(db_session: Session) -> list[Provider]:
    """Cria prestadores validados para a categoria encanador (PLUMBER)."""
    p1 = Provider(
        id="prov-plumber-1",
        name="Mário Encanamentos",
        category=ProviderCategory.PLUMBER.value,
        region="Rio de Janeiro",
        phone="+55 21 99999-0001",
        is_validated=True,
        rating=4.9,
    )
    p2 = Provider(
        id="prov-plumber-2",
        name="Luigi Hidráulica Express",
        category=ProviderCategory.PLUMBER.value,
        region="Rio de Janeiro",
        phone="+55 21 99999-0002",
        is_validated=True,
        rating=4.7,
    )
    db_session.add_all([p1, p2])
    db_session.commit()
    return [p1, p2]


# ==============================================================================
# 1. TESTES DO SERVIÇO DE AGENDAMENTO (URGÊNCIA × AGENDA)
# ==============================================================================


def test_scheduling_urgent_ticket_with_guest_conflict(
    db_session: Session, sample_property: Property
) -> None:
    """Ticket URGENT com hóspede presente deve agendar imediatamente e notificar o inquilino."""
    today = date.today()
    booking = Booking(
        id="book-urgent-conflict",
        property_id=sample_property.id,
        guest_name="Carlos Hóspede",
        guest_contact="+55 21 98888-7777",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=3),
    )
    db_session.add(booking)

    ticket = MaintenanceTicket(
        id="tick-urgent-1",
        run_id="run-urgent-1",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PLUMBER.value,
        urgency=TicketUrgency.URGENT.value,
        location_in_property="Banheiro suíte",
        description="Vazamento grave inundando o piso.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    proposal = find_optimal_schedule(
        db=db_session,
        property_id=sample_property.id,
        urgency=ticket.urgency,
    )

    assert proposal.notify_tenant is True
    assert proposal.has_guest is True
    assert proposal.proposed_date > datetime.now(UTC)
    assert "Horário emergencial" in proposal.slot_description


def test_scheduling_urgent_ticket_without_guest(
    db_session: Session, sample_property: Property
) -> None:
    """Ticket URGENT sem hóspede deve agendar no primeiro horário sem notificar inquilino."""
    ticket = MaintenanceTicket(
        id="tick-urgent-no-guest",
        run_id="run-urgent-no-guest",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.CLEANER.value,
        category=ProviderCategory.ELECTRICIAN.value,
        urgency=TicketUrgency.URGENT.value,
        location_in_property="Quadro elétrico",
        description="Cheiro de queimado no disjuntor principal.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    proposal = find_optimal_schedule(
        db=db_session,
        property_id=sample_property.id,
        urgency=ticket.urgency,
    )

    assert proposal.notify_tenant is False
    assert proposal.has_guest is False


def test_scheduling_normal_ticket_finds_gap_between_bookings(
    db_session: Session, sample_property: Property
) -> None:
    """Ticket não urgente deve escolher uma data em janela sem hóspedes."""
    today = date.today()
    # Reserva 1: de hoje até +2 dias
    b1 = Booking(
        id="book-gap-1",
        property_id=sample_property.id,
        guest_name="Hóspede Atual",
        guest_contact="+55 21 91111-2222",
        start_date=today,
        end_date=today + timedelta(days=2),
    )
    # Reserva 2: de +5 dias até +8 dias (janela livre nos dias +3 e +4)
    b2 = Booking(
        id="book-gap-2",
        property_id=sample_property.id,
        guest_name="Próximo Hóspede",
        guest_contact="+55 21 93333-4444",
        start_date=today + timedelta(days=5),
        end_date=today + timedelta(days=8),
    )
    db_session.add_all([b1, b2])

    ticket = MaintenanceTicket(
        id="tick-normal-gap",
        run_id="run-normal-gap",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.GENERAL_MAINTENANCE.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Porta da varanda",
        description="Fechadura emperrando um pouco ao fechar.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    proposal = find_optimal_schedule(
        db=db_session,
        property_id=sample_property.id,
        urgency=ticket.urgency,
    )

    assert proposal.notify_tenant is False
    assert proposal.has_guest is False
    # Deve ser no intervalo sem hóspedes
    assert proposal.proposed_date.date() in (
        today + timedelta(days=3),
        today + timedelta(days=4),
    )


def test_scheduling_normal_ticket_fully_booked_falls_back(
    db_session: Session, sample_property: Property
) -> None:
    """Ticket normal sem janelas vagas cai no fallback com aviso ao inquilino."""
    today = date.today()
    # Bloqueia os próximos 20 dias com reserva contínua
    booking = Booking(
        id="book-full",
        property_id=sample_property.id,
        guest_name="Estadia Longa",
        guest_contact="+55 21 99999-8888",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=20),
    )
    db_session.add(booking)

    ticket = MaintenanceTicket(
        id="tick-normal-full",
        run_id="run-normal-full",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PAINTER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Sala",
        description="Pintura descascando perto da janela.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    proposal = find_optimal_schedule(
        db=db_session,
        property_id=sample_property.id,
        urgency=ticket.urgency,
    )

    assert proposal.notify_tenant is True
    assert proposal.has_guest is True


# ==============================================================================
# 2. TESTES DE TIMEOUTS E LEMBRETES (APScheduler / Fallback)
# ==============================================================================


def test_timeout_registration_and_cancellation() -> None:
    """Registra um timeout de orçamento e cancela com sucesso."""
    clear_active_timeouts()
    callback_executed = False

    def on_timeout(ticket_id: str, run_id: str) -> None:
        nonlocal callback_executed
        callback_executed = True

    job_id = register_quote_timeout(
        ticket_id="tick-timeout-001",
        run_id="run-timeout-001",
        timeout_minutes=60,
        callback=on_timeout,
    )
    assert job_id == "timeout_quote_tick-timeout-001"
    assert "timeout_quote_tick-timeout-001" in get_active_timeouts()

    canceled = cancel_timeout_job(job_id)
    assert canceled is True
    assert "timeout_quote_tick-timeout-001" not in get_active_timeouts()
    assert callback_executed is False


def test_register_adm_reminder() -> None:
    """Registra lembrete para aprovação humana do ADM e cancela."""
    clear_active_timeouts()

    def on_reminder(ticket_id: str, run_id: str) -> None:
        pass

    job_id = register_adm_reminder(
        ticket_id="tick-reminder-001",
        run_id="run-reminder-001",
        reminder_minutes=30,
        callback=on_reminder,
    )
    assert job_id == "reminder_adm_tick-reminder-001"
    assert "reminder_adm_tick-reminder-001" in get_active_timeouts()

    canceled = cancel_timeout_job(job_id)
    assert canceled is True
    assert "reminder_adm_tick-reminder-001" not in get_active_timeouts()


def test_timeout_registration_with_apscheduler() -> None:
    """Verifica agendamento e cancelamento quando um scheduler APScheduler é fornecido."""
    from unittest.mock import MagicMock

    mock_scheduler = MagicMock()
    clear_active_timeouts()

    def dummy_cb(ticket_id: str, run_id: str) -> None:
        pass

    job_id = register_quote_timeout(
        ticket_id="tick-sched-1",
        run_id="run-sched-1",
        timeout_minutes=45,
        callback=dummy_cb,
        scheduler=mock_scheduler,
    )
    assert mock_scheduler.add_job.called

    job_adm_id = register_adm_reminder(
        ticket_id="tick-sched-adm-1",
        run_id="run-sched-adm-1",
        reminder_minutes=20,
        callback=dummy_cb,
        scheduler=mock_scheduler,
    )
    assert mock_scheduler.add_job.call_count == 2

    cancel_timeout_job(job_id, scheduler=mock_scheduler)
    cancel_timeout_job(job_adm_id, scheduler=mock_scheduler)
    assert mock_scheduler.remove_job.call_count == 2


# ==============================================================================
# 3. TESTES DA MÁQUINA DE ESTADOS LANGGRAPH (NÓ 3)
# ==============================================================================


@pytest.mark.asyncio
async def test_langgraph_happy_path_with_tenant_notification(
    db_session: Session,
    sample_property: Property,
    sample_providers: list[Provider],
) -> None:
    """Fluxo com hóspede presente:

    Ticket urgente agenda com conflito, acionando o nó de aviso ao inquilino e concluindo.
    """
    today = date.today()
    booking = Booking(
        id="book-happy-guest",
        property_id=sample_property.id,
        guest_name="Mariana Hóspede",
        guest_contact="+55 21 97777-6666",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=5),
    )
    db_session.add(booking)

    ticket = MaintenanceTicket(
        id="tick-happy-guest-001",
        run_id="run-happy-guest-001",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PLUMBER.value,
        urgency=TicketUrgency.URGENT.value,
        location_in_property="Banheiro",
        description="Chuveiro vazando água fervente.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(
        ticket_id=ticket.id,
        property_id=sample_property.id,
        run_id=ticket.run_id,
    )

    await starter.astart_resolution(req, db=db_session)

    # Retoma com aprovação do ADM
    selected_provider = sample_providers[0]
    final_state = await resume_resolution(
        ticket_id=ticket.id,
        provider_id=selected_provider.id,
        graph=compiled_resolver_graph,
    )

    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.RESOLVED.value
    assert ticket.selected_provider_id == selected_provider.id
    assert ticket.notify_tenant is True
    assert final_state.get("notify_tenant") is True
    assert final_state.get("status") == TicketStatus.RESOLVED.value


@pytest.mark.asyncio
async def test_langgraph_happy_path_interrupt_and_resume(
    db_session: Session,
    sample_property: Property,
    sample_providers: list[Provider],
) -> None:
    """Fluxo feliz:

    1. Ticket OPEN
    2. Grafo executa nós 1, 2 e 3 e PAUSA no interrupt para aprovação do ADM.
    3. Status fica AWAITING_ADM_APPROVAL e cotações são salvas.
    4. resume_resolution é chamado com provider escolhido.
    5. Grafo conclui agendamento determinístico e finaliza com status RESOLVED.
    """
    ticket = MaintenanceTicket(
        id="tick-happy-001",
        run_id="run-happy-001",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PLUMBER.value,
        urgency=TicketUrgency.URGENT.value,
        location_in_property="Cozinha",
        description="Torneira da pia quebrou e está vazando.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(
        ticket_id=ticket.id,
        property_id=sample_property.id,
        run_id=ticket.run_id,
    )

    # Executa até a interrupção humana do ADM
    state_after_pause = await starter.astart_resolution(req, db=db_session)

    # Verifica pausa
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.AWAITING_ADM_APPROVAL.value
    quotes = db_session.query(Quote).filter(Quote.ticket_id == ticket.id).all()
    assert len(quotes) >= 1
    assert all(q.status == QuoteStatus.RECEIVED.value for q in quotes)
    assert state_after_pause.get("status") == TicketStatus.AWAITING_ADM_APPROVAL.value

    # ADM escolhe o prestador 1
    selected_provider = sample_providers[0]
    final_state = await resume_resolution(
        ticket_id=ticket.id,
        provider_id=selected_provider.id,
        graph=compiled_resolver_graph,
    )

    # Verifica resolução final
    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.RESOLVED.value
    assert ticket.selected_provider_id == selected_provider.id
    assert ticket.scheduled_date is not None
    assert final_state.get("status") == TicketStatus.RESOLVED.value


@pytest.mark.asyncio
async def test_langgraph_alternative_path_no_providers(
    db_session: Session, sample_property: Property
) -> None:
    """Quando não há prestadores validados para a categoria, aciona o fallback."""
    ticket = MaintenanceTicket(
        id="tick-no-prov-001",
        run_id="run-no-prov-001",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PAINTER.value,  # Categoria sem nenhum prestador cadastrado
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Quarto",
        description="Pintura descascada na parede.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(
        ticket_id=ticket.id,
        property_id=sample_property.id,
        run_id=ticket.run_id,
    )

    result = await starter.astart_resolution(req, db=db_session)

    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.NO_PROVIDERS_FALLBACK.value
    assert result.get("status") == TicketStatus.NO_PROVIDERS_FALLBACK.value


@pytest.mark.asyncio
async def test_langgraph_alternative_path_refusal_loop(
    db_session: Session,
    sample_property: Property,
    sample_providers: list[Provider],
) -> None:
    """Quando o prestador recusa a primeira data proposta, o grafo tenta uma nova data."""
    ticket = MaintenanceTicket(
        id="tick-refuse-001",
        run_id="run-refuse-001",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PLUMBER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Área de serviço",
        description="Tanque entupido.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(
        ticket_id=ticket.id,
        property_id=sample_property.id,
        run_id=ticket.run_id,
    )

    # Inicia com refuse_dates_count=1 (recusará a 1ª data e aceitará a 2ª)
    await starter.astart_resolution(req, db=db_session, refuse_dates_count=1)

    # Retoma aprovação com prestador 2
    selected_provider = sample_providers[1]
    final_state = await resume_resolution(
        ticket_id=ticket.id,
        provider_id=selected_provider.id,
        graph=compiled_resolver_graph,
    )

    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.RESOLVED.value
    assert ticket.selected_provider_id == selected_provider.id
    # Houve pelo menos 1 recusa registrada
    assert final_state.get("retry_date_count", 0) >= 1


@pytest.mark.asyncio
async def test_langgraph_alternative_path_max_refusals_escalates(
    db_session: Session,
    sample_property: Property,
    sample_providers: list[Provider],
) -> None:
    """Quando o prestador recusa 3 vezes a data, escalona para o ADM humano."""
    ticket = MaintenanceTicket(
        id="tick-escalate-001",
        run_id="run-escalate-001",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PLUMBER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Lavabo",
        description="Válvula de descarga travando.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(ticket)
    db_session.commit()

    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(
        ticket_id=ticket.id,
        property_id=sample_property.id,
        run_id=ticket.run_id,
    )

    # Inicia com refuse_dates_count=3
    await starter.astart_resolution(req, db=db_session, refuse_dates_count=3)

    selected_provider = sample_providers[0]
    final_state = await resume_resolution(
        ticket_id=ticket.id,
        provider_id=selected_provider.id,
        graph=compiled_resolver_graph,
    )

    db_session.refresh(ticket)
    assert ticket.status == TicketStatus.ESCALATED_TO_ADM.value
    assert final_state.get("status") == TicketStatus.ESCALATED_TO_ADM.value


@pytest.mark.asyncio
async def test_langgraph_starter_idempotency(
    db_session: Session,
    sample_property: Property,
) -> None:
    """Se o ticket já estiver resolvido, a chamada do starter é ignorada."""
    ticket = MaintenanceTicket(
        id="tick-idempotent-001",
        run_id="run-idempotent-001",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PLUMBER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Varanda",
        description="Ralo lento.",
        status=TicketStatus.RESOLVED.value,
    )
    db_session.add(ticket)
    db_session.commit()

    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(
        ticket_id=ticket.id,
        property_id=sample_property.id,
        run_id=ticket.run_id,
    )

    result = await starter.astart_resolution(req, db=db_session)
    assert result == {}


def test_langgraph_sync_starter_call(
    monkeypatch: pytest.MonkeyPatch,
    sample_property: Property,
    db_session: Session,
) -> None:
    """Verifica chamada síncrona exigida pelo protocolo ResolverStarter."""
    ticket = MaintenanceTicket(
        id="tick-sync-001",
        run_id="run-sync-001",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.CLEANER.value,
        category=ProviderCategory.PLUMBER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Lavanderia",
        description="Filtro da máquina sujo.",
        status=TicketStatus.RESOLVED.value,  # Mantém resolvido para execução rápida
    )
    db_session.add(ticket)
    db_session.commit()

    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(
        ticket_id=ticket.id,
        property_id=sample_property.id,
        run_id=ticket.run_id,
    )
    # Não deve levantar exceções
    starter.start_resolution(req)


# ==============================================================================
# 4. TESTES DA API HTTP DE TICKETS (/api/tickets e /api/properties/{id}/tickets)
# ==============================================================================


def test_api_list_tickets_and_filters(
    client: TestClient,
    db_session: Session,
    sample_property: Property,
) -> None:
    """Testa listagem de chamados e filtros por property_id e status."""
    t1 = MaintenanceTicket(
        id="tick-api-1",
        run_id="run-api-1",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PLUMBER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Cozinha",
        description="Goteira leve.",
        status=TicketStatus.OPEN.value,
    )
    t2 = MaintenanceTicket(
        id="tick-api-2",
        run_id="run-api-2",
        property_id="other-property",
        reported_by_role=ReportedByRole.CLEANER.value,
        category=ProviderCategory.ELECTRICIAN.value,
        urgency=TicketUrgency.URGENT.value,
        location_in_property="Quarto",
        description="Tomada faíscando.",
        status=TicketStatus.RESOLVED.value,
    )
    db_session.add_all([t1, t2])
    db_session.commit()

    # Listagem geral
    resp = client.get("/api/tickets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) >= 2

    # Filtro por imóvel
    resp_prop = client.get(f"/api/tickets?property_id={sample_property.id}")
    assert resp_prop.status_code == 200
    assert all(t["property_id"] == sample_property.id for t in resp_prop.json())

    # Filtro por status
    resp_status = client.get("/api/tickets?status_filter=resolved")
    assert resp_status.status_code == 200
    assert all(t["status"] == "resolved" for t in resp_status.json())


def test_api_get_ticket_details(
    client: TestClient,
    db_session: Session,
    sample_property: Property,
) -> None:
    """Testa obtenção de detalhes do chamado por ID (200 e 404)."""
    t = MaintenanceTicket(
        id="tick-detail-1",
        run_id="run-detail-1",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PLUMBER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Banheiro",
        description="Ralo com escoamento lento.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(t)
    db_session.commit()

    resp = client.get(f"/api/tickets/{t.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == t.id

    resp_404 = client.get("/api/tickets/non-existent-id")
    assert resp_404.status_code == 404


def test_api_list_ticket_quotes(
    client: TestClient,
    db_session: Session,
    sample_property: Property,
    sample_providers: list[Provider],
) -> None:
    """Testa listagem de cotações associadas a um chamado."""
    t = MaintenanceTicket(
        id="tick-quotes-1",
        run_id="run-quotes-1",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PLUMBER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Banheiro",
        description="Troca de sifão.",
        status=TicketStatus.AWAITING_ADM_APPROVAL.value,
    )
    db_session.add(t)
    db_session.flush()

    q1 = Quote(
        id="quote-api-1",
        ticket_id=t.id,
        run_id=t.run_id,
        provider_id=sample_providers[0].id,
        amount=180.0,
        description="Troca simples de sifão.",
        status=QuoteStatus.RECEIVED.value,
    )
    db_session.add(q1)
    db_session.commit()

    resp = client.get(f"/api/tickets/{t.id}/quotes")
    assert resp.status_code == 200
    quotes = resp.json()
    assert len(quotes) == 1
    assert quotes[0]["amount"] == 180.0

    resp_404 = client.get("/api/tickets/unknown-ticket/quotes")
    assert resp_404.status_code == 404


@pytest.mark.asyncio
async def test_api_approve_ticket_endpoint_validation_and_success(
    client: TestClient,
    db_session: Session,
    sample_property: Property,
    sample_providers: list[Provider],
) -> None:
    """Testa validações de erro e sucesso no endpoint POST /api/tickets/{id}/approve."""
    # 1. Erro 404: ticket não existe
    resp_404 = client.post(
        "/api/tickets/unknown/approve",
        json={"run_id": "r1", "provider_id": "p1"},
    )
    assert resp_404.status_code == 404

    # 2. Erro 400: ticket não está aguardando aprovação do ADM (está OPEN)
    t = MaintenanceTicket(
        id="tick-app-val-1",
        run_id="run-app-val-1",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PLUMBER.value,
        urgency=TicketUrgency.URGENT.value,
        location_in_property="Cozinha",
        description="Vazamento.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(t)
    db_session.commit()

    resp_bad_status = client.post(
        f"/api/tickets/{t.id}/approve",
        json={"run_id": t.run_id, "provider_id": sample_providers[0].id},
    )
    assert resp_bad_status.status_code == 400
    assert "não está aguardando aprovação" in resp_bad_status.json()["detail"]

    # 3. Executa o starter para levar o ticket até o ponto de pausa (AWAITING_ADM_APPROVAL)
    starter = LangGraphResolverStarter(compiled_resolver_graph)
    req = ResolutionRequest(ticket_id=t.id, property_id=sample_property.id, run_id=t.run_id)
    await starter.astart_resolution(req, db=db_session)
    db_session.expire_all()

    # 4. Erro 400: prestador sem cotação
    resp_bad_provider = client.post(
        f"/api/tickets/{t.id}/approve",
        json={"run_id": t.run_id, "provider_id": "non-existent-prov"},
    )
    assert resp_bad_provider.status_code == 400
    assert "Não foi encontrada cotação" in resp_bad_provider.json()["detail"]

    # 5. Sucesso: aprova com o prestador 1
    resp_success = client.post(
        f"/api/tickets/{t.id}/approve",
        json={"run_id": t.run_id, "provider_id": sample_providers[0].id},
    )
    assert resp_success.status_code == 200
    body = resp_success.json()
    assert body["status"] == TicketStatus.RESOLVED.value
    assert body["selected_provider_id"] == sample_providers[0].id
    assert body["scheduled_date"] is not None


def test_api_list_tickets_for_property(
    client: TestClient,
    db_session: Session,
    sample_property: Property,
) -> None:
    """Testa endpoint GET /api/properties/{property_id}/tickets."""
    t = MaintenanceTicket(
        id="tick-prop-tickets-1",
        run_id="run-prop-tickets-1",
        property_id=sample_property.id,
        reported_by_role=ReportedByRole.TENANT.value,
        category=ProviderCategory.PLUMBER.value,
        urgency=TicketUrgency.NORMAL.value,
        location_in_property="Lavabo",
        description="Troca de lâmpada.",
        status=TicketStatus.OPEN.value,
    )
    db_session.add(t)
    db_session.commit()

    resp = client.get(f"/api/properties/{sample_property.id}/tickets")
    assert resp.status_code == 200
    tickets = resp.json()
    assert len(tickets) >= 1
    assert tickets[0]["id"] == t.id

    resp_404 = client.get("/api/properties/non-existent-prop/tickets")
    assert resp_404.status_code == 404
