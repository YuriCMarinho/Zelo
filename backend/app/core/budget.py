"""Módulo de controle de orçamento e custos de inferência LLM (Featherless / Mock).

Implementa tabelas de preços, estimativa preventiva, cálculo exato,
verificação de tetos (por run e global), alertas e persistência.
"""

import logging
from collections.abc import Sequence

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models.cost import CostRecord
from app.schemas.cost import CostSummary

logger = logging.getLogger("smartrepair.budget")

# Tabela de preços de referência da Featherless (US$ por 1.000.000 de tokens)
# Conforme docs/COST.md
MODEL_PRICING: dict[str, dict[str, float]] = {
    "Qwen/Qwen3.5-4B": {
        "input": 0.10,
        "output": 0.20,
    },
    "Qwen/Qwen3.5-9B": {
        "input": 0.17,
        "output": 0.25,
    },
    "Qwen/Qwen3.5-27B": {
        "input": 0.30,
        "output": 2.40,
    },
    "mock": {
        "input": 0.0,
        "output": 0.0,
    },
}

# Ledger em memória para fallback/testes sem DB ativo
_in_memory_run_costs: dict[str, float] = {}
_in_memory_global_cost: float = 0.0


class BudgetExceededError(Exception):
    """Lançada quando uma chamada excede os limites de custo configurados."""

    def __init__(
        self,
        message: str,
        current_cost: float,
        limit: float,
        scope: str = "run",
    ) -> None:
        super().__init__(message)
        self.current_cost = current_cost
        self.limit = limit
        self.scope = scope


def reset_in_memory_costs() -> None:
    """Reseta o acumulador em memória (útil para testes)."""
    global _in_memory_run_costs, _in_memory_global_cost
    _in_memory_run_costs.clear()
    _in_memory_global_cost = 0.0


def calculate_call_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """Calcula o custo exato em USD de uma chamada ao LLM.

    Fórmula: (input_tokens * price_in + output_tokens * price_out) / 1.000.000
    """
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["mock"])
    cost = (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000.0
    return round(cost, 8)


def estimate_call_cost(model: str, estimated_input_tokens: int, max_tokens: int) -> float:
    """Estima o custo preventivo considerando o pior caso de tokens de saída (max_tokens)."""
    return calculate_call_cost(model, estimated_input_tokens, max_tokens)


def evaluate_budget_alert(spent_usd: float, limit_usd: float) -> str | None:
    """Avalia se o gasto acumulado atingiu os patamares de alerta (50%, 75%, 90% ou excedido)."""
    if limit_usd <= 0.0:
        return None

    ratio = spent_usd / limit_usd
    if ratio >= 1.0:
        return "BUDGET_EXCEEDED"
    if ratio >= 0.90:
        return "ALERT_90"
    if ratio >= 0.75:
        return "ALERT_75"
    if ratio >= 0.50:
        return "ALERT_50"
    return None


def check_budget_before_call(
    run_id: str,
    estimated_cost: float,
    db: Session | None = None,
    max_run_cost: float | None = None,
    max_global_cost: float | None = None,
) -> None:
    """Verifica se o custo projetado excede o teto por run_id ou global antes da chamada.

    Lança BudgetExceededError com corte automático se ultrapassar 100%.
    """
    run_ceiling = max_run_cost if max_run_cost is not None else settings.max_cost_per_run_usd
    global_ceiling = (
        max_global_cost if max_global_cost is not None else settings.max_cost_global_usd
    )

    if db is not None:
        # Consulta histórico por run_id no banco
        run_spent_query = select(func.coalesce(func.sum(CostRecord.cost_usd), 0.0)).where(
            CostRecord.run_id == run_id
        )
        run_spent = float(db.execute(run_spent_query).scalar_one())

        # Consulta histórico global no banco
        global_spent_query = select(func.coalesce(func.sum(CostRecord.cost_usd), 0.0))
        global_spent = float(db.execute(global_spent_query).scalar_one())
    else:
        run_spent = _in_memory_run_costs.get(run_id, 0.0)
        global_spent = _in_memory_global_cost

    projected_run = run_spent + estimated_cost
    if projected_run > run_ceiling:
        msg = (
            f"Custo projetado para a execução '{run_id}' ({projected_run:.6f} USD) "
            f"excede o teto de {run_ceiling:.4f} USD."
        )
        logger.error(
            msg,
            extra={"run_id": run_id, "projected": projected_run, "limit": run_ceiling},
        )
        raise BudgetExceededError(msg, current_cost=projected_run, limit=run_ceiling, scope="run")

    projected_global = global_spent + estimated_cost
    if projected_global > global_ceiling:
        msg = (
            f"Custo global acumulado projetado ({projected_global:.6f} USD) "
            f"excede o teto de {global_ceiling:.4f} USD."
        )
        logger.error(
            msg, extra={"projected_global": projected_global, "limit": global_ceiling}
        )
        raise BudgetExceededError(
            msg, current_cost=projected_global, limit=global_ceiling, scope="global"
        )

    # Verifica alertas estruturados preventivos
    alert_run = evaluate_budget_alert(projected_run, run_ceiling)
    if alert_run:
        logger.warning(
            "Alerta de orçamento por execução",
            extra={"run_id": run_id, "alert": alert_run, "projected": projected_run},
        )

    alert_global = evaluate_budget_alert(projected_global, global_ceiling)
    if alert_global:
        logger.warning(
            "Alerta de orçamento global",
            extra={"alert": alert_global, "projected_global": projected_global},
        )


def record_call_cost(
    db: Session | None,
    run_id: str,
    node: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    is_mock: bool = True,
) -> CostRecord:
    """Registra uma chamada de LLM e seu custo associado no DB e no acumulador."""
    global _in_memory_run_costs, _in_memory_global_cost

    # Atualiza acumulador em memória
    _in_memory_run_costs[run_id] = _in_memory_run_costs.get(run_id, 0.0) + cost_usd
    _in_memory_global_cost += cost_usd

    record = CostRecord(
        run_id=run_id,
        node=node,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        is_mock=is_mock,
    )

    if db is not None:
        db.add(record)
        db.commit()
        db.refresh(record)

    return record


def get_cost_summary(db: Session, run_id: str | None = None) -> CostSummary:
    """Retorna o sumário consolidado de custos e alertas a partir do banco de dados."""
    query = select(CostRecord)
    limit_usd = settings.max_cost_global_usd

    if run_id is not None:
        query = query.where(CostRecord.run_id == run_id)
        limit_usd = settings.max_cost_per_run_usd

    records: Sequence[CostRecord] = db.execute(query).scalars().all()

    total_cost_usd = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    total_calls = len(records)
    by_node: dict[str, float] = {}
    by_model: dict[str, float] = {}

    for r in records:
        total_cost_usd += r.cost_usd
        total_input_tokens += r.input_tokens
        total_output_tokens += r.output_tokens
        by_node[r.node] = round(by_node.get(r.node, 0.0) + r.cost_usd, 6)
        by_model[r.model] = round(by_model.get(r.model, 0.0) + r.cost_usd, 6)

    total_cost_usd = round(total_cost_usd, 6)
    percentage_used = round((total_cost_usd / limit_usd) * 100, 2) if limit_usd > 0 else 0.0
    alert_triggered = evaluate_budget_alert(total_cost_usd, limit_usd)

    return CostSummary(
        total_cost_usd=total_cost_usd,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        total_calls=total_calls,
        by_node=by_node,
        by_model=by_model,
        budget_limit_usd=limit_usd,
        percentage_used=percentage_used,
        alert_triggered=alert_triggered,
    )
