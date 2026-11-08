"""Módulo determinístico de detecção de Prompt Injection e abuso de entrada.

Protege os agentes contra instruções maliciosas originadas de canais não confiáveis
(hóspedes, camareiras, prestadores de serviço e simuladores).
"""

import re

MAX_INPUT_LENGTH = 1500

# Expressões regulares determinísticas para identificar tentativas de injeção
# Cobre padrões comuns em inglês e português
INJECTION_PATTERNS = [
    # Inglês - Instruções e regras do sistema
    (
        re.compile(
            r"(?i)\b(ignore|disregard|forget|override)\s+(all\s+)?(previous|prior|above|system)?\s*(instructions|prompts|rules|commands|constraints)\b"
        ),
        "Instruction override (English)",
    ),
    (
        re.compile(r"(?i)\b(system\s+prompt|reveal\s+prompt|show\s+prompt|print\s+instructions)\b"),
        "System prompt extraction (English)",
    ),
    (
        re.compile(
            r"(?i)\b(you\s+are\s+now|act\s+as|pretend\s+you\s+are|jailbreak|dan\s+mode|developer\s+mode)\b"
        ),
        "Persona hijacking / Jailbreak (English)",
    ),
    (
        re.compile(r"(?i)\b(system\s+override|admin\s+override|root\s+access|bypass\s+safety)\b"),
        "Privilege escalation (English)",
    ),
    # Português - Instruções e regras do sistema
    (
        re.compile(
            r"(?i)\b(ignore|desconsidere|esque[çc]a)\s+(as|todas\s+as)?\s*(instru[çc][õo]es|regras|comandos|diretrizes)\s*(anteriores|do\s+sistema|passadas)?\b"
        ),
        "Subversão de instrução (Português)",
    ),
    (
        re.compile(
            r"(?i)\b(revele|mostre|imprima|exiba)\s+(o\s+|as\s+)?(prompt|instru[çc][õo]es|regras)\s*(do\s+sistema|de\s+sistema)?\b"
        ),
        "Extração de prompt do sistema (Português)",
    ),
    (
        re.compile(
            r"(?i)\b((?:finja|pretend[ae])\s+que\s+voc[êe]\s+[ée]|aja\s+como|agora\s+voc[êe]\s+[ée]|modo\s+dan|desbloqueado)\b"
        ),
        "Sequestro de persona (Português)",
    ),
    (
        re.compile(
            r"(?i)\b(me\s+d[êe]\s+a\s+senha|forne[çc]a\s+o\s+token|me\s+passe\s+o\s+token|burlar\s+regras)\b"
        ),
        "Tentativa de exfiltração ou bypass (Português)",
    ),
]


def detect_prompt_injection(text: str) -> tuple[bool, str | None]:
    """Analisa um texto não confiável e identifica se há tentativa de prompt injection.

    Retorna:
        (is_injection, reason)
    """
    if not text:
        return False, None

    # Normaliza espaços em branco e quebras de linha para regex robusto
    cleaned = " ".join(text.split())

    for pattern, description in INJECTION_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            return True, f"{description}: correspondência encontrada com '{match.group(0)}'"

    return False, None
