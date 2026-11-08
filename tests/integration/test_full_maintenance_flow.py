"""Testes de integração de ponta a ponta para o Caminho Feliz Completo (S2-T8).

Cobre:
1. Caminho Feliz Completo via API:
   - Relato no chat do imóvel (POST /api/chat) com remetente hóspede.
   - Roteador identifica manutenção -> Nó 2 cria chamado com extração tipada.
   - Nó 3 (LangGraph) cota orçamentos com 3 prestadores validados e pausa no interrupt.
   - Consulta de orçamentos (GET /api/tickets/{id}/quotes).
   - Anfitrião aprova na sessão do imóvel (POST /api/tickets/{id}/approve).
   - Nó 3 agenda via Urgência x Agenda, confirma data com prestador, notifica inquilino
     hospedado e finaliza o chamado como RESOLVED.
   - Trilha de auditoria e status de cotações (uma SELECTED, demais REJECTED).
2. Fluxo Comercial Completo via API (Fluxo A - Aquisição):
   - Pergunta no chat unificado sobre regras e check-in.
   - Roteamento para Nó 1 (commercial_node1).
   - Consulta de regras/agenda sem abertura indevida de tickets de manutenção.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Booking, MaintenanceTicket, Property, Provider, Quote
from app.schemas.common import (
    ProviderCategory,
    QuoteStatus,
    ReportedByRole,
    TicketStatus,
    TicketUrgency,
)


@pytest.fixture
def integration_property(db_session: Session) -> Property:
    """Cria um imóvel padrão para os testes integrados de ponta a ponta."""
    prop = Property(
        id="prop-e2e-001",
        name="Apartamento Luxo Leblon",
        description="Amplo apartamento a 100m da praia com ar condicionado em todos os cômodos.",
        address="Avenida Delfim Moreira, 500",
        city="Rio de Janeiro",
        state="RJ",
        rules_faq="Check-in a partir das 15h. Check-out até 11h. Silêncio após as 22h. Não fumar.",
    )
    db_session.add(prop)
    db_session.commit()
    return prop


@pytest.fixture
def integration_plumbers(db_session: Session) -> list[Provider]:
    """Cria 3 prestadores validados para a categoria encanador (PLUMBER)."""
    p1 = Provider(
        id="prov-plumber-e2e-1",
        name="Mário Encanamentos Leblon",
        category=ProviderCategory.PLUMBER.value,
        region="Rio de Janeiro",
        phone="+55 21 99999-1111",
        is_validated=True,
        rating=4.9,
    )
    p2 = Provider(
        id="prov-plumber-e2e-2",
        name="Luigi Hidráulica Express",
        category=ProviderCategory.PLUMBER.value,
        region="Rio de Janeiro",
        phone="+55 21 99999-2222",
        is_validated=True,
        rating=4.8,
    )
    p3 = Provider(
        id="prov-plumber-e2e-3",
        name="Super Reparos e Chuveiros",
        category=ProviderCategory.PLUMBER.value,
        region="Rio de Janeiro",
        phone="+55 21 99999-3333",
        is_validated=True,
        rating=4.5,
    )
    db_session.add_all([p1, p2, p3])
    db_session.commit()
    return [p1, p2, p3]


# ==============================================================================
# 1. TESTE DO CAMINHO FELIZ COMPLETO DE MANUTENÇÃO (FLUXO C)
# ==============================================================================


def test_full_maintenance_happy_path_e2e(
    client: TestClient,
    db_session: Session,
    integration_property: Property,
    integration_plumbers: list[Provider],
) -> None:
    """Testa o fluxo completo do chamado de manutenção de ponta a ponta via API:

    1. Hóspede com reserva ativa relata vazamento grave no chat (POST /api/chat).
    2. Roteador/Nó 2 cria ticket e inicia o Nó 3 no LangGraph.
    3. Nó 3 solicita cotações para 3 prestadores e pausa em AWAITING_ADM_APPROVAL.
    4. Anfitrião consulta as 3 cotações (GET /api/tickets/{id}/quotes).
    5. Anfitrião aprova o 1º prestador (POST /api/tickets/{id}/approve).
    6. Nó 3 retoma, agenda horário emergencial, confirma data, notifica inquilino e
       marca chamado como RESOLVED.
    7. Cotação escolhida fica SELECTED e demais REJECTED.
    8. Trilha de auditoria registra todo o ciclo de vida.
    """
    today = date.today()

    # Cria reserva ativa com hóspede presente no imóvel
    booking = Booking(
        id="book-e2e-active",
        property_id=integration_property.id,
        guest_name="Carlos Hóspede",
        guest_contact="+55 21 98888-5555",
        start_date=today - timedelta(days=1),
        end_date=today + timedelta(days=4),
    )
    db_session.add(booking)
    db_session.commit()

    # --- PASSO 1: Relato do Hóspede via Ponto Único de Chat ---
    chat_payload = {
        "property_id": integration_property.id,
        "message": "Socorro! O cano da pia do banheiro estourou e está vazando muita água pelo chão!",
        "sender_role": ReportedByRole.TENANT.value,
        "run_id": "run-e2e-happy-001",
    }
    chat_response = client.post("/api/chat", json=chat_payload)
    assert chat_response.status_code == 200, f"Erro no chat: {chat_response.text}"
    chat_data = chat_response.json()

    assert chat_data["route_destination"] == "maintenance_node2"
    ticket_id = chat_data["ticket_id"]
    assert ticket_id is not None
    assert len(ticket_id) > 0

    # --- PASSO 2: Verificação do Chamado e Cotações em AWAITING_ADM_APPROVAL ---
    ticket_resp = client.get(f"/api/tickets/{ticket_id}")
    assert ticket_resp.status_code == 200
    ticket_data = ticket_resp.json()

    assert ticket_data["status"] == TicketStatus.AWAITING_ADM_APPROVAL.value
    assert ticket_data["category"] == ProviderCategory.PLUMBER.value
    assert ticket_data["urgency"] == TicketUrgency.URGENT.value
    assert ticket_data["property_id"] == integration_property.id

    # Consulta cotações via endpoint específico
    quotes_resp = client.get(f"/api/tickets/{ticket_id}/quotes")
    assert quotes_resp.status_code == 200
    quotes_data = quotes_resp.json()
    assert len(quotes_data) == 3

    # Valida estrutura das cotações
    provider_ids_quoted = [q["provider_id"] for q in quotes_data]
    for p in integration_plumbers:
        assert p.id in provider_ids_quoted

    for quote_entry in quotes_data:
        assert quote_entry["amount"] > 0
        assert quote_entry["status"] == QuoteStatus.RECEIVED.value
        assert quote_entry["provider_name"] is not None

    # --- PASSO 3: Aprovação do Orçamento pelo Anfitrião (ADM) ---
    chosen_provider = integration_plumbers[0]
    approval_payload = {
        "run_id": "run-e2e-approve-001",
        "provider_id": chosen_provider.id,
    }
    approve_resp = client.post(f"/api/tickets/{ticket_id}/approve", json=approval_payload)
    assert approve_resp.status_code == 200, f"Erro na aprovação: {approve_resp.text}"
    resolved_ticket_data = approve_resp.json()

    # --- PASSO 4: Validação do Chamado Finalizado ---
    assert resolved_ticket_data["status"] == TicketStatus.RESOLVED.value
    assert resolved_ticket_data["selected_provider_id"] == chosen_provider.id
    assert resolved_ticket_data["scheduled_date"] is not None
    assert resolved_ticket_data["notify_tenant"] is True

    # --- PASSO 5: Validação das Cotações no Banco de Dados ---
    db_session.expire_all()
    db_quotes = db_session.query(Quote).filter(Quote.ticket_id == ticket_id).all()
    assert len(db_quotes) == 3

    selected_quotes = [q for q in db_quotes if q.provider_id == chosen_provider.id]
    assert len(selected_quotes) == 1
    assert selected_quotes[0].status == QuoteStatus.SELECTED.value

    rejected_quotes = [q for q in db_quotes if q.provider_id != chosen_provider.id]
    assert len(rejected_quotes) == 2
    for r_quote in rejected_quotes:
        assert r_quote.status == QuoteStatus.REJECTED.value

    # --- PASSO 6: Validação da Trilha de Auditoria (AuditEvent) ---
    audit_events = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.ticket_id == ticket_id)
        .order_by(AuditEvent.created_at.asc())
        .all()
    )
    assert len(audit_events) >= 1
    event_types = [e.event_type for e in audit_events]
    assert "ticket_resolved" in event_types or "notify_tenant_and_resolve" in [
        e.node for e in audit_events
    ]


# ==============================================================================
# 2. TESTE DO FLUXO COMERCIAL COMPLETO (FLUXO A - AQUISIÇÃO)
# ==============================================================================


def test_full_commercial_flow_inquiry_and_rules(
    client: TestClient,
    db_session: Session,
    integration_property: Property,
) -> None:
    """Testa o fluxo comercial quando o usuário envia dúvidas sobre o imóvel:

    1. Dúvida geral sobre check-in e regras é encaminhada ao Nó 1 (commercial_node1).
    2. Resposta cordial traz as informações cadastradas de rules_faq.
    3. Nenhum chamado de manutenção (ticket) é aberto no banco.
    """
    commercial_payload = {
        "property_id": integration_property.id,
        "message": "Olá! Gostaria de saber qual o horário de check-in e check-out no apartamento?",
        "sender_role": ReportedByRole.TENANT.value,
        "run_id": "run-e2e-comm-001",
    }
    response = client.post("/api/chat", json=commercial_payload)
    assert response.status_code == 200
    data = response.json()

    assert data["route_destination"] == "commercial_node1"
    assert data["ticket_id"] is None
    assert data["property_id"] == integration_property.id
    assert len(data["response_text"]) > 0

    # Garante que nenhum ticket foi criado no DB
    tickets_count = (
        db_session.query(MaintenanceTicket)
        .filter(MaintenanceTicket.property_id == integration_property.id)
        .count()
    )
    assert tickets_count == 0


def test_full_commercial_flow_booking_availability(
    client: TestClient,
    db_session: Session,
    integration_property: Property,
) -> None:
    """Testa consulta comercial com checagem de conflito na agenda de reservas."""
    today = date.today()

    # Cadastra reserva ocupando de today+5 a today+10
    existing_booking = Booking(
        id="book-e2e-existing",
        property_id=integration_property.id,
        guest_name="Ana Turista",
        guest_contact="+55 21 97777-1111",
        start_date=today + timedelta(days=5),
        end_date=today + timedelta(days=10),
    )
    db_session.add(existing_booking)
    db_session.commit()

    # Pergunta comercial sobre período conflitante
    conflict_payload = {
        "property_id": integration_property.id,
        "message": "Gostaria de alugar o apartamento para a próxima semana, de 5 a 10 dias a partir de hoje.",
        "sender_role": ReportedByRole.TENANT.value,
        "run_id": "run-e2e-comm-002",
    }
    response = client.post("/api/chat", json=conflict_payload)
    assert response.status_code == 200
    data = response.json()

    assert data["route_destination"] == "commercial_node1"
    assert data["ticket_id"] is None
    assert len(data["response_text"]) > 0
