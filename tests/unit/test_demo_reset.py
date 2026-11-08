"""Testes unitários para o endpoint de reset de demonstração (POST /api/demo/reset)."""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, MaintenanceTicket, Property, Provider, Quote


def test_demo_reset_cleans_transient_data_and_reseeds(
    client: TestClient,
    db_session: Session,
) -> None:
    """Valida se o reset de demonstração limpa chamados e restaura o banco de dados."""
    # 1. Cria um prestador, ticket e cotação de teste simulando dados sujos
    prov = Provider(
        id="prov-dirty-001",
        name="Prestador Teste",
        category="plumber",
        region="Rio de Janeiro",
        phone="+5511999990001",
    )
    db_session.add(prov)
    db_session.commit()

    prop = Property(
        id="prop-test-dirty",
        name="Imóvel Sujo",
        city="Rio",
        state="RJ",
        address="Rua A",
        description="Desc",
    )
    db_session.add(prop)
    db_session.commit()

    ticket = MaintenanceTicket(
        run_id="run-dirty-001",
        property_id=prop.id,
        reported_by_role="tenant",
        category="plumber",
        urgency="urgent",
        location_in_property="Cozinha",
        description="Vazamento grave",
        status="open",
    )
    db_session.add(ticket)
    db_session.commit()

    quote = Quote(
        ticket_id=ticket.id,
        provider_id=prov.id,
        amount=350.0,
        run_id="run-dirty-001",
        status="pending",
    )
    db_session.add(quote)
    db_session.commit()

    assert db_session.query(MaintenanceTicket).count() >= 1
    assert db_session.query(Quote).count() >= 1

    # 2. Executa a chamada de reset da demonstração
    resp = client.post("/api/demo/reset")
    assert resp.status_code == 200
    data = resp.json()

    assert data["status"] == "success"
    assert "reinicializado com sucesso" in data["message"]
    assert data["properties_count"] >= 3

    # 3. Confere se os chamados antigos foram excluídos e ticket padrão da demo foi restaurado
    assert db_session.query(Quote).count() == 0
    assert (
        db_session.query(MaintenanceTicket)
        .filter(MaintenanceTicket.run_id == "run-dirty-001")
        .count()
        == 0
    )
    assert (
        db_session.query(MaintenanceTicket)
        .filter(MaintenanceTicket.id == "ticket-demo-01")
        .count()
        == 1
    )

    # 4. Confere se o evento de auditoria foi gravado
    audit = (
        db_session.query(AuditEvent)
        .filter(AuditEvent.event_type == "DEMO_RESET")
        .first()
    )
    assert audit is not None
    assert audit.node == "system_demo"
