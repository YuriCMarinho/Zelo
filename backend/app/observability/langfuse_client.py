"""Wrapper de observabilidade Langfuse com fallback offline/mock e mascaramento LGPD.

Garante que todos os spans e traces injetem run_id como trace_id, mascarem PII
e registrem uso de tokens e custo explícito calculado em USD.
"""

import logging
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.config import settings
from app.security.masking import mask_dict_pii, mask_pii

logger = logging.getLogger("smartrepair.observability")


class SpanRecord(BaseModel):
    """Representação estruturada de um span/geração registrado no Langfuse."""

    trace_id: str = Field(..., description="ID da execução (run_id) propagado")
    node: str = Field(..., description="Nome do nó executor")
    model: str = Field(..., description="Modelo utilizado ou mock")
    input_data: Any = Field(..., description="Entrada sanitizada e com PII mascarada")
    output_data: Any = Field(..., description="Saída sanitizada e com PII mascarada")
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    is_mock: bool = Field(default=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LangfuseClientWrapper:
    """Wrapper para envio de telemetria e custo ao Langfuse com buffer em memória."""

    def __init__(self) -> None:
        self._traces: list[SpanRecord] = []
        self._client: Any = None
        self._initialized = False

    def _init_client(self) -> None:
        """Inicializa o SDK do Langfuse sob demanda caso as chaves não sejam mock."""
        if self._initialized:
            return

        self._initialized = True
        if settings.langfuse_public_key in ("mock-public", "", None):
            logger.info("Langfuse operando em modo OFFLINE/MOCK (chaves mock).")
            return

        try:
            from langfuse import Langfuse  # type: ignore[import-not-found,import-untyped]

            self._client = Langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                host=settings.langfuse_host,
            )
            logger.info("Cliente Langfuse conectado com sucesso.")
        except Exception as exc:
            logger.warning(
                "Não foi possível inicializar SDK do Langfuse; operando em modo offline.",
                extra={"error": str(exc)},
            )
            self._client = None

    def record_generation(
        self,
        run_id: str,
        node: str,
        model: str,
        messages: Any,
        output: Any,
        input_tokens: int,
        output_tokens: int,
        cost_usd: float,
        is_mock: bool = True,
        offline_only: bool = False,
    ) -> SpanRecord:
        """Registra uma geração LLM aplicando mascaramento LGPD e vinculando ao run_id."""
        if not offline_only:
            self._init_client()

        # Mascara estritamente PII nos dados enviados
        masked_input = mask_dict_pii(messages)
        masked_output = mask_pii(str(output)) if isinstance(output, str) else mask_dict_pii(output)

        total_tokens = input_tokens + output_tokens

        span = SpanRecord(
            trace_id=run_id,
            node=node,
            model=model,
            input_data=masked_input,
            output_data=masked_output,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            cost_usd=cost_usd,
            is_mock=is_mock,
        )

        self._traces.append(span)

        # Se houver cliente Langfuse real ativo, envia span com custo explícito
        if self._client is not None and not offline_only:
            try:
                trace = self._client.trace(id=run_id, name=f"run-{run_id}")
                trace.generation(
                    name=f"node-{node}",
                    model=model,
                    input=masked_input,
                    output=masked_output,
                    usage={
                        "input": input_tokens,
                        "output": output_tokens,
                        "total": total_tokens,
                        "unit": "TOKENS",
                    },
                    usage_details={
                        "input_cost": (cost_usd * (input_tokens / max(1, total_tokens))),
                        "output_cost": (cost_usd * (output_tokens / max(1, total_tokens))),
                        "total_cost": cost_usd,
                    },
                )
            except Exception as exc:
                logger.warning(
                    "Falha ao enviar geração ao Langfuse; mantido no buffer local.",
                    extra={"error": str(exc)},
                )

        return span

    def get_recorded_traces(self) -> list[SpanRecord]:
        """Retorna todos os spans/gerações registrados em memória."""
        return list(self._traces)

    def get_traces_by_run_id(self, run_id: str) -> list[SpanRecord]:
        """Filtra os spans registrados por run_id específico."""
        return [t for t in self._traces if t.trace_id == run_id]

    def clear_traces(self) -> None:
        """Limpa o buffer local de traces (útil para suíte de testes)."""
        self._traces.clear()


# Instância singleton para uso por todo o backend
langfuse_client = LangfuseClientWrapper()
