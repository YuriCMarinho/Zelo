"""Suíte de Testes de Segurança e Conformidade LGPD (S2-T8).

Cobre:
- Mascaramento e anonimização de dados de identificação pessoal (PII) de acordo com a LGPD:
  1. Telefones de hóspedes e prestadores (+55, DDD, fixo, celular)
  2. CPFs (formatados com pontuação e brutos de 11 dígitos)
  3. E-mails pessoais
  4. Chaves de API, Tokens Bearer e senhas
- Mascaramento recursivo em dicionários e listas (mask_dict_pii)
- Validação nas respostas de endpoints públicos da API (/api/providers)
- Verificação de não exposição de dados claros em trilhas de auditoria (AuditEvent)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import AuditEvent, Provider
from app.schemas.common import ProviderCategory, mask_phone
from app.security.masking import mask_dict_pii, mask_pii

# ==============================================================================
# 1. TESTES UNITÁRIOS DE MASCARAMENTO DE PII (TELEFONES, CPFS, E-MAILS, CHAVES)
# ==============================================================================


@pytest.mark.parametrize(
    ("raw_text", "expected_fragment"),
    [
        # Telefones celulares e fixos com diferentes formatações
        ("Meu telefone é +55 11 98765-4321 para contato.", "[TELEFONE_REDACTED]"),
        ("Favor ligar no (21) 99888-7766 urgente.", "[TELEFONE_REDACTED]"),
        ("WhatsApp: 11 988776655 falar com Carlos.", "[TELEFONE_REDACTED]"),
        ("Contato comercial fixo: 3344-5566 em horário comercial.", "[TELEFONE_REDACTED]"),
        # CPFs com e sem formatação
        ("CPF do hóspede: 123.456.789-00 registrado.", "[CPF_REDACTED]"),
        ("Documento sem pontos: 12345678900 para a reserva.", "[CPF_REDACTED]"),
        # E-mails
        ("Envie o voucher para hospede.exemplo@provedor.com.br por favor.", "[EMAIL_REDACTED]"),
        ("Contato financeiro: cobranca@smartrepair.ai", "[EMAIL_REDACTED]"),
        # Segredos, Chaves de API e Tokens
        ("Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9", "Bearer [SECRET_REDACTED]"),
        ("Chave Featherless: sk-abcdef1234567890abcdef123456", "[SECRET_REDACTED]"),
        ("api_key='super_secret_token_12345'", "[SECRET_REDACTED]"),
        ("senha: 'minha_senha_super_secreta'", "[SECRET_REDACTED]"),
    ],
)
def test_mask_pii_string_replacements(raw_text: str, expected_fragment: str) -> None:
    """Garante que dados sensíveis são devidamente anonimizados pela função mask_pii."""
    masked = mask_pii(raw_text)
    assert expected_fragment in masked

    # Garante que números de telefone e CPFs não sobraram em texto claro
    assert "98765-4321" not in masked
    assert "123.456.789-00" not in masked
    assert "12345678900" not in masked
    assert "hospede.exemplo@provedor.com.br" not in masked
    assert "sk-abcdef1234567890abcdef123456" not in masked


def test_mask_phone_public_display_formatting() -> None:
    """Verifica formatação segura de exibição pública de telefones (mask_phone)."""
    assert mask_phone("+55 21 99999-0001") == "(55) *********-01"
    assert mask_phone("+55 11 98888-5555") == "(55) *********-55"
    assert mask_phone(None) == ""
    assert mask_phone("123") == "***"


# ==============================================================================
# 2. TESTES DE MASCARAMENTO ESTRUTURADO (DICIONÁRIOS E LISTAS RECURSIVOS)
# ==============================================================================


def test_mask_dict_pii_recursive() -> None:
    """Garante que estruturas aninhadas de metadados e payloads têm seu PII mascarado."""
    nested_data = {
        "guest": {
            "name": "Maria Silva",
            "contact": "+55 21 97777-8888",
            "cpf": "987.654.321-99",
            "email": "maria@teste.com",
        },
        "providers": [
            {"id": "prov-1", "phone": "+55 11 96666-5555"},
            {"id": "prov-2", "phone": "(31) 95555-4444"},
        ],
        "metadata": {
            "headers": {
                "Authorization": "Bearer token_secreto_super_longo_123456",
            },
            "status_code": 200,
            "is_active": True,
        },
    }

    masked_data = mask_dict_pii(nested_data)

    # Telefones mascarados
    assert masked_data["guest"]["contact"] == "[TELEFONE_REDACTED]"
    assert masked_data["providers"][0]["phone"] == "[TELEFONE_REDACTED]"
    assert masked_data["providers"][1]["phone"] == "[TELEFONE_REDACTED]"

    # CPF e E-mail mascarados
    assert masked_data["guest"]["cpf"] == "[CPF_REDACTED]"
    assert masked_data["guest"]["email"] == "[EMAIL_REDACTED]"

    # Token Bearer mascarado
    assert masked_data["metadata"]["headers"]["Authorization"] == "Bearer [SECRET_REDACTED]"

    # Tipos primitivos mantidos
    assert masked_data["metadata"]["status_code"] == 200
    assert masked_data["metadata"]["is_active"] is True


# ==============================================================================
# 3. VERIFICAÇÃO EM ENDPOINTS DA API HTTP (GET /api/providers)
# ==============================================================================


def test_api_providers_returns_masked_phone(
    client: TestClient,
    db_session: Session,
) -> None:
    """Garante que a listagem pública de prestadores via GET /api/providers

    exibe o telefone devidamente mascarado (LGPD) e nunca o telefone original.
    """
    prov = Provider(
        id="prov-lgpd-test-1",
        name="Cláudio Encanador",
        category=ProviderCategory.PLUMBER.value,
        region="São Paulo",
        phone="+55 11 99876-5432",
        is_validated=True,
        rating=4.9,
    )
    db_session.add(prov)
    db_session.commit()

    response = client.get("/api/providers?category=plumber")
    assert response.status_code == 200
    data = response.json()

    target = next((p for p in data if p["id"] == prov.id), None)
    assert target is not None

    # Telefone formatado de forma anônima
    assert target["masked_phone"] == "(55) *********-32"

    # Telefone real em texto claro nunca deve aparecer na resposta JSON
    assert "99876-5432" not in response.text


# ==============================================================================
# 4. VERIFICAÇÃO NA TRILHA DE AUDITORIA (AUDITEVENT)
# ==============================================================================


def test_audit_event_persists_safely_without_cleartext_pii(
    client: TestClient,
    db_session: Session,
) -> None:
    """Verifica que eventos de auditoria com detalhes de contato mascaram

    o conteúdo antes de serem armazenados ou consultados via GET /api/audit.
    """
    raw_details = {
        "tenant_phone": "+55 21 98888-9999",
        "tenant_email": "inquilino@ferias.com.br",
        "action": "guest_notified",
    }
    safe_details = mask_dict_pii(raw_details)

    audit = AuditEvent(
        run_id="run-lgpd-audit-001",
        ticket_id="tick-lgpd-001",
        node="notify_tenant_and_resolve",
        event_type="tenant_notified",
        payload=safe_details,
    )
    db_session.add(audit)
    db_session.commit()

    # Consulta via endpoint de auditoria
    resp = client.get("/api/audit?ticket_id=tick-lgpd-001")
    assert resp.status_code == 200
    audit_data = resp.json()

    assert len(audit_data) >= 1
    record = audit_data[0]
    payload = record["payload"]

    assert payload["tenant_phone"] == "[TELEFONE_REDACTED]"
    assert payload["tenant_email"] == "[EMAIL_REDACTED]"
    assert "98888-9999" not in resp.text
    assert "inquilino@ferias.com.br" not in resp.text


# ==============================================================================
# 5. VERIFICAÇÃO DE MASCARAMENTO NOS LOGS DE APLICAÇÃO (PIIMaskingFilter)
# ==============================================================================


def test_logger_masks_pii_in_log_records(caplog: pytest.LogCaptureFixture) -> None:
    """Verifica que o PIIMaskingFilter intercepta mensagens de log contendo dados sensíveis

    (telefones, CPFs, tokens) e grava as versões anonimizadas.
    """
    import logging

    from app.observability.logger import PIIMaskingFilter

    test_logger = logging.getLogger("test.lgpd.logger")
    test_logger.setLevel(logging.INFO)
    test_logger.addFilter(PIIMaskingFilter())

    with caplog.at_level(logging.INFO, logger="test.lgpd.logger"):
        test_logger.info(
            "Hóspede realizou check-in. Telefone: +55 11 98765-4321, CPF: 123.456.789-00."
        )

    assert len(caplog.records) >= 1
    log_msg = caplog.records[-1].message

    assert "[TELEFONE_REDACTED]" in log_msg
    assert "[CPF_REDACTED]" in log_msg
    assert "98765-4321" not in log_msg
    assert "123.456.789-00" not in log_msg


# ==============================================================================
# 6. VERIFICAÇÃO DE MASCARAMENTO NOS TRACES/SPANS DO LANGFUSE
# ==============================================================================


def test_langfuse_client_masks_pii_in_recorded_spans() -> None:
    """Garante que spans enviados ao Langfuse têm entradas e saídas estritamente mascaradas."""
    from app.observability.langfuse_client import LangfuseClientWrapper

    wrapper = LangfuseClientWrapper()
    raw_messages = [
        {"role": "system", "content": "Assistente virtual do imóvel."},
        {
            "role": "user",
            "content": "Meu WhatsApp é +55 21 99999-1234 e CPF 999.888.777-66, favor agendar.",
        },
    ]
    raw_output = "Confirmado para o titular com contato (21) 98888-0000 e email hospede@email.com"

    span = wrapper.record_generation(
        run_id="run-lgpd-langfuse-001",
        node="resolver_quote_request",
        model="Qwen/Qwen3.5-4B",
        messages=raw_messages,
        output=raw_output,
        input_tokens=30,
        output_tokens=20,
        cost_usd=0.0001,
        is_mock=True,
    )

    # Verifica entrada mascarada
    input_str = str(span.input_data)
    assert "[TELEFONE_REDACTED]" in input_str
    assert "[CPF_REDACTED]" in input_str
    assert "99999-1234" not in input_str
    assert "999.888.777-66" not in input_str

    # Verifica saída mascarada
    output_str = str(span.output_data)
    assert "[TELEFONE_REDACTED]" in output_str
    assert "[EMAIL_REDACTED]" in output_str
    assert "98888-0000" not in output_str
    assert "hospede@email.com" not in output_str
