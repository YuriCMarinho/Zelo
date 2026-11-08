"""Bateria de testes End-to-End (E2E) com modelos reais da Featherless.

Valida a integração real e o parsing de respostas para:
- Roteador Barato (Qwen/Qwen3.5-4B)
- Nó 1 Comercial (Qwen/Qwen3.5-9B)
- Nó 2 Validador com extração estruturada (Qwen/Qwen3.5-4B)
- Nó 3 Síntese de orçamentos para o ADM (Qwen/Qwen3.5-9B)
- Contabilidade de custos no Ledger e telemetria Langfuse

Os testes com chamadas de rede reais são decorados com @pytest.mark.real_llm e só rodam
quando explicitamente invocados (-m real_llm) e com FEATHERLESS_API_KEY configurada.
Testes de protocolo com API mockada garantem 100% de cobertura do branch de rede Featherless.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.commercial import handle_commercial_message
from app.agents.router import route_chat_message
from app.agents.validator import handle_maintenance_message
from app.core.budget import get_cost_summary
from app.core.config import settings
from app.core.llm import generate
from app.db.models import CostRecord, Property
from app.schemas.common import ReportedByRole, RouteDestination


class MockClassificationFormat(BaseModel):
    category: str = Field(..., description="Categoria do prestador")
    urgency: str = Field(..., description="Urgência do chamado")
    location: str = Field(..., description="Cômodo do imóvel")


@pytest.fixture
def featherless_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Configura o ambiente para modo Featherless com verificação de chave."""
    api_key = os.environ.get("FEATHERLESS_API_KEY", "").strip()
    if not api_key or api_key == "mock-key":
        pytest.skip(
            "FEATHERLESS_API_KEY ausente ou não configurada no ambiente. "
            "Defina FEATHERLESS_API_KEY para rodar os testes de rede reais."
        )
    monkeypatch.setattr(settings, "llm_mode", "featherless")
    monkeypatch.setattr(settings, "featherless_api_key", api_key)


# =====================================================================
# 1. Testes de Protocolo Featherless (Simulando API HTTP Real)
# =====================================================================


@pytest.mark.asyncio
async def test_featherless_client_parses_chat_completion_and_records_cost(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Testa o branch Featherless do cliente LLM simulando payload de retorno real."""
    monkeypatch.setattr(settings, "llm_mode", "featherless")
    monkeypatch.setattr(settings, "featherless_api_key", "sk-featherless-test-key")

    mock_http_response = MagicMock()
    mock_http_response.status_code = 200
    mock_http_response.raise_for_status = MagicMock()
    mock_http_response.json.return_value = {
        "id": "chatcmpl-test-001",
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Olá! Temos Wi-Fi de 500Mbps e vaga de garagem coberta.",
                }
            }
        ],
        "usage": {
            "prompt_tokens": 120,
            "completion_tokens": 25,
            "total_tokens": 145,
        },
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_http_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = await generate(
            messages=[{"role": "user", "content": "Tem Wi-Fi e garagem?"}],
            model="Qwen/Qwen3.5-9B",
            max_tokens=256,
            run_id="run-featherless-test-01",
            node="commercial_test",
            db=db_session,
        )

    assert resp.is_mock is False
    assert resp.model == "Qwen/Qwen3.5-9B"
    assert "Wi-Fi" in resp.content
    assert resp.input_tokens == 120
    assert resp.output_tokens == 25
    # Custo Qwen 9B: (120 * 0.17 + 25 * 0.25) / 1_000_000 = (20.4 + 6.25)/1M = 0.00002665
    assert resp.cost_usd > 0.0

    # Confere gravação no banco de dados
    record = (
        db_session.query(CostRecord)
        .filter(CostRecord.run_id == "run-featherless-test-01")
        .first()
    )
    assert record is not None
    assert record.model == "Qwen/Qwen3.5-9B"
    assert record.is_mock is False
    assert record.cost_usd == resp.cost_usd


@pytest.mark.asyncio
async def test_featherless_client_parses_json_markdown_block(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Testa parsing de response_format estruturado retornado em markdown json."""
    monkeypatch.setattr(settings, "llm_mode", "featherless")
    monkeypatch.setattr(settings, "featherless_api_key", "sk-test-key")

    mock_http_response = MagicMock()
    mock_http_response.raise_for_status = MagicMock()
    mock_http_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        '```json\n{"category": "plumber", "urgency": "urgent", '
                        '"location": "Cozinha"}\n```'
                    ),
                }
            }
        ],
        "usage": {"prompt_tokens": 80, "completion_tokens": 20},
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = mock_http_response
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        resp = await generate(
            messages=[{"role": "user", "content": "Pia entupida na cozinha"}],
            model="Qwen/Qwen3.5-4B",
            max_tokens=128,
            run_id="run-structured-json-01",
            node="validator_test",
            response_format=MockClassificationFormat,
            db=db_session,
        )

    assert resp.is_mock is False
    assert isinstance(resp.parsed, MockClassificationFormat)
    assert resp.parsed.category == "plumber"
    assert resp.parsed.location == "Cozinha"


@pytest.mark.asyncio
async def test_featherless_protocol_full_flow_chain(
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valida a cadeia completa de atendimento e triagem simulando a API Featherless."""
    monkeypatch.setattr(settings, "llm_mode", "featherless")
    monkeypatch.setattr(settings, "featherless_api_key", "sk-test-live-key")

    prop = Property(
        id="prop-e2e-chain-01",
        name="Cobertura Duplex Ipanema",
        city="Rio de Janeiro",
        state="RJ",
        address="Av. Vieira Souto, 100",
        description="Cobertura de luxo com vista frontal para a praia de Ipanema.",
        rules_faq="Check-in a partir das 15h. Silêncio após as 22h.",
    )
    db_session.add(prop)
    db_session.commit()

    # 1. Simula resposta da Featherless para o Nó 1 Comercial
    comm_resp = MagicMock()
    comm_resp.raise_for_status = MagicMock()
    comm_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": (
                        "Olá! A cobertura conta com terraço amplo, piscina privativa "
                        "e vista deslumbrante."
                    ),
                }
            }
        ],
        "usage": {"prompt_tokens": 150, "completion_tokens": 40},
    }

    mock_client = AsyncMock()
    mock_client.post.return_value = comm_resp
    mock_client.__aenter__.return_value = mock_client
    mock_client.__aexit__.return_value = None

    with patch("httpx.AsyncClient", return_value=mock_client):
        comm_out = await handle_commercial_message(
            prop=prop,
            message="Gostaria de saber se a piscina é aquecida e se tem churrasqueira?",
            run_id="run-e2e-comm-chain-01",
            db=db_session,
        )

    assert comm_out.route_destination == RouteDestination.COMMERCIAL_NODE1
    assert "cobertura conta com terraço" in comm_out.response_text

    # 2. Simula resposta da Featherless para o Nó 2 Validador
    val_resp = MagicMock()
    val_resp.raise_for_status = MagicMock()
    val_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "Confirmação de triagem: problema hidráulico no banheiro social.",
                }
            }
        ],
        "usage": {"prompt_tokens": 180, "completion_tokens": 30},
    }
    mock_client.post.return_value = val_resp

    with patch("httpx.AsyncClient", return_value=mock_client):
        reply, ticket_id = await handle_maintenance_message(
            prop=prop,
            message="O chuveiro do banheiro social não está esquentando e sai apenas água fria.",
            sender_role=ReportedByRole.TENANT,
            run_id="run-e2e-val-chain-02",
            db=db_session,
        )

    assert ticket_id is not None
    assert "chamado de manutenção" in reply.lower()

    # 3. Confere auditoria de custos no ledger
    summary = get_cost_summary(db=db_session)
    assert summary.total_cost_usd > 0.0
    records = db_session.query(CostRecord).all()
    assert len(records) >= 2
    assert all(r.is_mock is False for r in records)


# =====================================================================
# 2. Testes Reais com API Featherless (@pytest.mark.real_llm)
# =====================================================================


@pytest.mark.real_llm
@pytest.mark.asyncio
async def test_live_featherless_router_classification(
    featherless_env: None,
    db_session: Session,
) -> None:
    """Valida o Roteador Barato com Qwen/Qwen3.5-4B real da Featherless."""
    # Mensagem ambígua de manutenção
    dest_maint = await route_chat_message(
        property_id="prop-copacabana-01",
        message="A ducha higiênica não fecha direito e está molhando o piso da suíte",
        sender_role=ReportedByRole.TENANT,
        run_id="run-live-router-maint-01",
        db=db_session,
    )
    assert dest_maint == RouteDestination.MAINTENANCE_NODE2

    # Mensagem ambígua de atendimento comercial
    dest_comm = await route_chat_message(
        property_id="prop-copacabana-01",
        message="Gostaria de saber se aceitam pet de pequeno porte e se há taxa extra",
        sender_role=ReportedByRole.TENANT,
        run_id="run-live-router-comm-01",
        db=db_session,
    )
    assert dest_comm == RouteDestination.COMMERCIAL_NODE1


@pytest.mark.real_llm
@pytest.mark.asyncio
async def test_live_featherless_commercial_node1(
    featherless_env: None,
    db_session: Session,
) -> None:
    """Valida o Nó 1 Comercial com Qwen/Qwen3.5-9B real da Featherless."""
    prop = Property(
        id="prop-live-01",
        name="Loft Beira Mar Leblon",
        city="Rio de Janeiro",
        state="RJ",
        address="Av. Delfim Moreira, 500",
        description="Loft moderno de frente para o mar com Wi-Fi veloz e cafeteira Nespresso.",
        rules_faq="Check-in às 15h. Silêncio após as 22h.",
    )
    db_session.add(prop)
    db_session.commit()

    output = await handle_commercial_message(
        prop=prop,
        message="Olá! O apartamento tem secador de cabelo e ferro de passar roupas?",
        run_id="run-live-commercial-01",
        db=db_session,
    )

    assert output.route_destination == RouteDestination.COMMERCIAL_NODE1
    assert len(output.response_text) > 30
    assert output.run_id == "run-live-commercial-01"

    summary = get_cost_summary(db=db_session)
    assert summary.total_cost_usd > 0.0


@pytest.mark.real_llm
@pytest.mark.asyncio
async def test_live_featherless_validator_node2(
    featherless_env: None,
    db_session: Session,
) -> None:
    """Valida o Nó 2 Validador com Qwen/Qwen3.5-4B real da Featherless."""
    prop = Property(
        id="prop-live-02",
        name="Chalé Montanha Gramado",
        city="Gramado",
        state="RS",
        address="Rua das Hortênsias, 100",
        description="Chalé aconchegante com lareira.",
        rules_faq="Não fumar.",
    )
    db_session.add(prop)
    db_session.commit()

    report_msg = (
        "Identifiquei um vazamento forte na torneira da pia da cozinha, "
        "a água está pingando sem parar dentro do armário inferior."
    )
    reply, ticket_id = await handle_maintenance_message(
        prop=prop,
        message=report_msg,
        sender_role=ReportedByRole.CLEANER,
        run_id="run-live-validator-01",
        db=db_session,
    )

    assert ticket_id is not None
    assert "chamado" in reply.lower() or "registrado" in reply.lower()


@pytest.mark.real_llm
@pytest.mark.asyncio
async def test_live_featherless_quote_synthesis_node3(
    featherless_env: None,
    db_session: Session,
) -> None:
    """Valida síntese comparativa de orçamentos com Qwen/Qwen3.5-9B real."""
    messages = [
        {
            "role": "system",
            "content": (
                "Você é o agente Zelo que auxilia anfitriões de temporada. "
                "Apresente uma síntese executiva clara comparando 3 orçamentos "
                "recebidos de prestadores para aprovação do anfitrião."
            ),
        },
        {
            "role": "user",
            "content": (
                "Chamado: Conserto de vazamento no sifão da cozinha.\n"
                "Orçamento 1: João Hidráulica - R$ 250,00 - Atendimento em 24h\n"
                "Orçamento 2: SOS Encanamentos - R$ 280,00 - Atendimento no mesmo dia\n"
                "Orçamento 3: Reparos Express - R$ 320,00 - Atendimento imediato"
            ),
        },
    ]

    resp = await generate(
        messages=messages,
        model="Qwen/Qwen3.5-9B",
        max_tokens=320,
        run_id="run-live-synthesis-01",
        node="resolver_adm_summary",
        db=db_session,
    )

    assert resp.is_mock is False
    assert len(resp.content) > 50
    assert resp.cost_usd > 0.0
