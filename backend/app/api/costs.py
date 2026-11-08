"""Endpoints HTTP para consulta de custos e orçamento da aplicação."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.budget import get_cost_summary
from app.db.session import get_db
from app.schemas.cost import CostSummary

router = APIRouter(prefix="/api/costs", tags=["Custos"])
DatabaseDep = Annotated[Session, Depends(get_db)]


@router.get(
    "/summary",
    response_model=CostSummary,
    summary="Resumo de consumo de orçamento",
    description="Retorna o consolidado de gastos em US$, total de chamadas, tokens e alertas.",
)
def get_costs_summary(
    db: DatabaseDep,
    run_id: str | None = None,
) -> CostSummary:
    return get_cost_summary(db, run_id=run_id)
