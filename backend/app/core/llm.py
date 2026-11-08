"""Cliente LLM com mock determinístico, respostas gravadas e Featherless API.

Implementa validação estrita de modelos permitidos, verificação obrigatória de max_tokens,
cálculo e auditoria preventiva de custos, e propagação de telemetria/LGPD via Langfuse.
"""

import asyncio
import json
from collections.abc import Sequence
from enum import Enum
from typing import Any, get_args, get_origin

import httpx
from pydantic import BaseModel, Field

from app.core.budget import (
    calculate_call_cost,
    check_budget_before_call,
    estimate_call_cost,
    record_call_cost,
)
from app.core.config import settings
from app.demo.replay import replay

# langfuse_client é importado sob demanda em generate() para evitar circular import
from app.observability.logger import logger

# Modelos homologados na Featherless conforme docs/COST.md
ALLOWED_MODELS = {
    "Qwen/Qwen3.5-4B",
    "Qwen/Qwen3.5-9B",
    "Qwen/Qwen3.5-27B",
}


class InvalidModelError(ValueError):
    """Lançada quando um modelo não homologado é solicitado."""

    pass


class MissingMaxTokensError(ValueError):
    """Lançada quando max_tokens não é informado ou é menor/igual a zero."""

    pass


class LLMResponse(BaseModel):
    """Resposta padronizada retornada por qualquer chamada LLM."""

    content: str = Field(..., description="Conteúdo textual gerado pelo modelo")
    parsed: Any | None = Field(
        default=None,
        description="Instância Pydantic validada quando response_format é fornecido",
    )
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    model: str = Field(..., description="Modelo executado")
    run_id: str = Field(..., description="ID da execução vinculado ao fluxo")
    node: str = Field(..., description="Nome do nó executor")
    is_mock: bool = Field(default=True)


def _generate_mock_instance(
    schema_cls: type[BaseModel], node: str, messages: list[dict[str, str]]
) -> BaseModel:
    """Gera deterministicamente uma instância válida de um schema Pydantic para modo mock."""
    field_values: dict[str, Any] = {}

    for field_name, field_info in schema_cls.model_fields.items():
        annotation = field_info.annotation

        # Trata Optional / Union
        origin = get_origin(annotation)
        args = get_args(annotation)
        if origin is None and args:
            pass
        elif origin is not None and type(None) in args:
            # Se for Optional e não obrigatório, pode manter None ou preencher valor
            non_none = [a for a in args if a is not type(None)]
            if non_none:
                annotation = non_none[0]

        # Tratamento por enum primeiro ou nome de campo contextual / tipo
        if isinstance(annotation, type) and issubclass(annotation, Enum):
            field_values[field_name] = next(iter(annotation))
        elif field_name == "run_id":
            field_values[field_name] = "run-mock-12345"
        elif field_name == "location_in_property":
            field_values[field_name] = "Banheiro da suíte master"
        elif field_name == "description":
            field_values[field_name] = "Vazamento na torneira sob a bancada"
        elif field_name == "intent":
            field_values[field_name] = "maintenance"
        elif field_name == "confidence":
            field_values[field_name] = 0.95
        elif field_name in ("property_id", "booking_id", "provider_id", "quote_id"):
            field_values[field_name] = f"mock-{field_name}"
        elif annotation is int:
            field_values[field_name] = 1
        elif annotation is float:
            field_values[field_name] = 100.0
        elif annotation is bool:
            field_values[field_name] = True
        elif annotation is str:
            field_values[field_name] = f"mock_{field_name}"
        elif origin in (list, Sequence):
            field_values[field_name] = []
        elif origin in (dict, dict):
            field_values[field_name] = {}
        elif isinstance(annotation, type) and issubclass(annotation, BaseModel):
            field_values[field_name] = _generate_mock_instance(annotation, node, messages)
        elif field_info.default is not None:
            field_values[field_name] = field_info.default
        elif field_info.default_factory is not None:
            field_values[field_name] = field_info.default_factory()  # type: ignore[call-arg]
        else:
            field_values[field_name] = f"mock_{field_name}"

    try:
        return schema_cls(**field_values)
    except Exception:
        # Fallback de validação caso algum campo necessite de valor default
        return schema_cls.model_construct(**field_values)


def _generate_mock_content(node: str, messages: list[dict[str, str]]) -> str:
    """Gera respostas textuais determinísticas e cordiais no modo mock."""
    last_user_msg = ""
    for m in reversed(messages):
        if m.get("role") in ("user", "guest", "cleaner", "provider"):
            last_user_msg = m.get("content", "")
            break

    if node == "router":
        maintenance_keywords = [
            "vaza",
            "torneira",
            "ar condicionado",
            "chuveiro",
            "quebr",
            "lâmpada",
            "manutenç",
            "consert",
        ]
        if any(w in last_user_msg.lower() for w in maintenance_keywords):
            return "Classificação: MANUTENÇÃO (encaminhado ao Nó 2 — Validador)."
        return "Classificação: COMERCIAL (encaminhado ao Nó 1 — Comercial)."

    if node in ("commercial", "commercial_node1"):
        return (
            "Olá! Seja muito bem-vindo ao nosso imóvel. Temos wi-fi de alta velocidade, "
            "cozinha completa e excelente localização. Deseja confirmar as datas da sua estadia?"
        )

    if node in ("validator", "validator_node2", "triage"):
        return (
            "Recebemos o relato de manutenção. Os detalhes foram classificados e encaminhados "
            "ao Nó 3 para cotação com prestadores validados."
        )

    if node == "resolver":
        return (
            "Orçamentos solicitados aos prestadores homologados. Propostas comparativas enviadas "
            "para aprovação na sessão do anfitrião."
        )

    return f"Resposta determinística simulada para o nó '{node}'."


async def generate(
    messages: list[dict[str, str]],
    model: str,
    max_tokens: int,
    *,
    run_id: str,
    node: str,
    temperature: float = 0.2,
    response_format: type[BaseModel] | None = None,
    db: Any = None,
) -> LLMResponse:
    """Gera uma resposta em modo mock, recorded_demo ou Featherless.

    Aplica validação rígida de modelo, obrigatoriedade de max_tokens, verificação
    de teto de custo antes da chamada e auditoria no Langfuse / DB.
    """
    # 1. Validação estrita de modelo permitido
    if model not in ALLOWED_MODELS:
        raise InvalidModelError(
            f"Modelo '{model}' não homologado. Modelos permitidos: {sorted(ALLOWED_MODELS)}"
        )

    # 2. Verificação obrigatória de max_tokens
    if max_tokens is None or max_tokens <= 0:
        raise MissingMaxTokensError(
            f"Parâmetro 'max_tokens' é obrigatório e deve ser > 0 (recebido: {max_tokens})."
        )

    # 3. Estimativa de tokens de entrada para verificação prévia de orçamento
    total_chars = sum(len(m.get("content", "")) for m in messages)
    estimated_input_tokens = max(10, total_chars // 4)

    # 4. Estimativa preventiva e verificação de teto orçamentário
    # Em modo mock o custo real será 0.0, mas a verificação orçamentária é validada
    mode = settings.llm_mode.lower()
    if mode == "real":
        mode = "featherless"
    if mode not in {"mock", "recorded_demo", "featherless"}:
        raise ValueError(f"LLM_MODE inválido: '{mode}'.")
    is_mock_mode = mode == "mock"
    cost_to_check = (
        0.0
        if mode != "featherless"
        else estimate_call_cost(model, estimated_input_tokens, max_tokens)
    )

    # A contingência continua disponível quando o orçamento de inferência se esgota.
    if mode != "recorded_demo":
        check_budget_before_call(run_id=run_id, estimated_cost=cost_to_check, db=db)

    # 5. Execução
    if mode == "recorded_demo":
        content = replay(node, model, messages)
        parsed = response_format.model_validate_json(content) if response_format else None
        await asyncio.sleep(settings.recorded_demo_latency_ms / 1000)
        input_tokens = estimated_input_tokens
        output_tokens = max(1, len(content) // 4)
        cost_usd = 0.0
        is_mock = True
    elif is_mock_mode:
        if response_format is not None:
            parsed = _generate_mock_instance(response_format, node, messages)
            content = parsed.model_dump_json()
        else:
            parsed = None
            content = _generate_mock_content(node, messages)

        input_tokens = estimated_input_tokens
        output_tokens = min(max_tokens, max(15, len(content) // 4))
        cost_usd = 0.0
        is_mock = True

    else:
        # Modo Featherless (API real)
        is_mock = False
        featherless_url = "https://api.featherless.ai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {settings.featherless_api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        # Qwen reasoning can consume the entire short response budget before
        # producing user-facing content. Request direct answers for these agents.
        if model.startswith("Qwen/Qwen3"):
            payload["chat_template_kwargs"] = {"enable_thinking": False}

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(featherless_url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = usage.get("prompt_tokens", estimated_input_tokens)
        output_tokens = usage.get("completion_tokens", len(content) // 4)
        cost_usd = calculate_call_cost(model, input_tokens, output_tokens)

        if response_format is not None:
            try:
                parsed = response_format.model_validate_json(content)
            except Exception:
                # Se vier formatado com markdown codeblock json
                cleaned = content.strip()
                if cleaned.startswith("```json"):
                    cleaned = cleaned[7:]
                if cleaned.startswith("```"):
                    cleaned = cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                parsed = response_format.model_validate(json.loads(cleaned.strip()))
        else:
            parsed = None

    # 6. Persistência de custo no banco de dados e acumulador em memória
    record_call_cost(
        db=db,
        run_id=run_id,
        node=node,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        is_mock=is_mock,
    )

    # 7. Telemetria e Spans no Langfuse com mascaramento e custo explícito
    from app.observability.langfuse_client import langfuse_client

    langfuse_client.record_generation(
        run_id=run_id,
        node=node,
        model=model,
        messages=messages,
        output=content,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        is_mock=is_mock,
        offline_only=mode == "recorded_demo",
    )

    logger.info(
        "Chamada LLM concluída",
        extra={
            "run_id": run_id,
            "node": node,
            "model": model,
            "llm_mode": mode,
            "cost_usd": cost_usd,
            "tokens": input_tokens + output_tokens,
        },
    )

    return LLMResponse(
        content=content,
        parsed=parsed,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        model=model,
        run_id=run_id,
        node=node,
        is_mock=is_mock,
    )
