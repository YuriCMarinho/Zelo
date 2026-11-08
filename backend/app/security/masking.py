"""Módulo de anonimização e mascaramento de PII (LGPD).

Garante que dados pessoais sensíveis (telefones de prestadores/hóspedes,
CPFs, e-mails e segredos/tokens) não vazem para logs, Langfuse ou código.
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any

# Padrões Regex para Detecção de PII
# Telefones brasileiros (com ou sem DDI +55, com ou sem DDD, fixos ou celulares)
PHONE_PATTERN = re.compile(
    r"(?:\+?55\s?)?(?:\(?0?[1-9]{2}\)?\s?)?(?:9\s?\d{4}[-\s]?\d{4}|\d{4}[-\s]?\d{4})\b"
)

# CPF formatado ou de 11 dígitos
CPF_FORMATTED_PATTERN = re.compile(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b")
CPF_RAW_PATTERN = re.compile(r"\b\d{11}\b")

# E-mail padrão
EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
)

# Chaves de API, Tokens Bearer e Segredos
BEARER_TOKEN_PATTERN = re.compile(r"\bBearer\s+[A-Za-z0-9_\-\.]{15,}\b", re.IGNORECASE)
FEATHERLESS_SK_PATTERN = re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b")
KEY_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|secret[_-]?key|token|password|senha)\s*[:=]\s*['\"]?[A-Za-z0-9_\-\.]{8,}['\"]?"
)


def mask_pii(text: str) -> str:
    """Mascara informações de identificação pessoal (PII) e credenciais em uma string.

    Substituições:
    - Telefones -> [TELEFONE_REDACTED]
    - CPFs -> [CPF_REDACTED]
    - E-mails -> [EMAIL_REDACTED]
    - Segredos/Tokens -> [SECRET_REDACTED]
    """
    if not text:
        return text

    masked = text

    # 1. Segredos e Tokens
    masked = BEARER_TOKEN_PATTERN.sub("Bearer [SECRET_REDACTED]", masked)
    masked = FEATHERLESS_SK_PATTERN.sub("[SECRET_REDACTED]", masked)
    masked = KEY_ASSIGNMENT_PATTERN.sub(r"\1: [SECRET_REDACTED]", masked)

    # 2. E-mails
    masked = EMAIL_PATTERN.sub("[EMAIL_REDACTED]", masked)

    # 3. CPFs com formatação e CPF sem formatação (11 dígitos contínuos)
    masked = CPF_FORMATTED_PATTERN.sub("[CPF_REDACTED]", masked)
    masked = CPF_RAW_PATTERN.sub("[CPF_REDACTED]", masked)

    # 4. Telefones com DDD ou DDI (ex.: (11) 98765-4321, +55 11 98765-4321, 11 988776655)
    explicit_phone = re.compile(
        r"(?:\+?55\s?)?(?:\(?0?[1-9]{2}\)?\s?)(?:9\s?\d{4}[-\s]?\d{4}|\d{4}[-\s]?\d{4})\b"
    )
    masked = explicit_phone.sub("[TELEFONE_REDACTED]", masked)

    # 5. Telefones locais restantes de 8 ou 9 dígitos com hífen (ex: 98765-4321 ou 3344-5566)
    local_phone = re.compile(r"\b(?:9\d{4}-\d{4}|\d{4}-\d{4})\b")
    masked = local_phone.sub("[TELEFONE_REDACTED]", masked)

    return masked


def mask_dict_pii(data: Any) -> Any:
    """Aplica mascaramento de PII recursivamente sobre dicionários, listas e tuplas."""
    if isinstance(data, str):
        return mask_pii(data)
    elif isinstance(data, Mapping):
        return {key: mask_dict_pii(value) for key, value in data.items()}
    elif isinstance(data, Sequence) and not isinstance(data, (bytes, bytearray)):
        return [mask_dict_pii(item) for item in data]
    return data
