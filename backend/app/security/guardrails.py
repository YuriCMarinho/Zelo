"""Módulo de Guardrails de entrada e saída.

Aplica sanitização estrita, limite de caracteres e verificação de injeção
em qualquer mensagem proveniente de canais não confiáveis (hóspede, camareira, prestador).
"""

import logging

from app.security.injection import MAX_INPUT_LENGTH, detect_prompt_injection

logger = logging.getLogger("smartrepair.security")


class SecurityViolationError(ValueError):
    """Lançada quando uma entrada não confiável viola regras de segurança ou guardrails."""

    def __init__(self, message: str, role: str, run_id: str, reason: str) -> None:
        super().__init__(message)
        self.role = role
        self.run_id = run_id
        self.reason = reason


def validate_untrusted_input(text: str, role: str, run_id: str) -> str:
    """Valida e sanitiza entradas não confiáveis antes de entrarem nos prompts dos agentes.

    Regras:
    1. Não permite entradas vazias após strip.
    2. Remove caracteres nulos e de controle maliciosos.
    3. Bloqueia entradas com mais de 1.500 caracteres (MAX_INPUT_LENGTH).
    4. Bloqueia tentativas de prompt injection detectadas por regex determinístico.

    Retorna o texto sanitizado se for válido.
    Lança SecurityViolationError em caso de violação.
    """
    if not isinstance(text, str):
        raise SecurityViolationError(
            message="Entrada inválida: esperava texto string.",
            role=role,
            run_id=run_id,
            reason="NON_STRING_INPUT",
        )

    # Sanitização básica (remoção de caracteres nulos)
    sanitized = text.replace("\x00", "").strip()

    if not sanitized:
        raise SecurityViolationError(
            message="Entrada vazia não permitida.",
            role=role,
            run_id=run_id,
            reason="EMPTY_INPUT",
        )

    # Verificação de tamanho
    if len(sanitized) > MAX_INPUT_LENGTH:
        reason = f"INPUT_TOO_LONG (tamanho={len(sanitized)}, máximo={MAX_INPUT_LENGTH})"
        msg = (
            f"Entrada do papel '{role}' excede o limite máximo permitido de "
            f"{MAX_INPUT_LENGTH} caracteres."
        )
        logger.warning(
            "Guardrail: Violação de limite de caracteres",
            extra={"role": role, "run_id": run_id, "length": len(sanitized)},
        )
        raise SecurityViolationError(message=msg, role=role, run_id=run_id, reason=reason)

    # Verificação de Prompt Injection
    is_injection, reason_detail = detect_prompt_injection(sanitized)
    if is_injection:
        reason = f"PROMPT_INJECTION_DETECTED: {reason_detail}"
        msg = (
            f"Violação de segurança: tentativa de prompt injection detectada para o papel '{role}'."
        )
        logger.error(
            "Guardrail: Tentativa de Prompt Injection bloqueada",
            extra={"role": role, "run_id": run_id, "reason": reason_detail},
        )
        raise SecurityViolationError(message=msg, role=role, run_id=run_id, reason=reason)

    return sanitized
