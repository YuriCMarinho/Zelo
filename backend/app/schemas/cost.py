from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema


class CostRecordCreate(BaseSchema):
    run_id: str = Field(..., min_length=1)
    node: str = Field(..., description="Nome do nó executor")
    model: str = Field(..., description="ID do modelo ou 'mock'")
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    is_mock: bool = Field(default=True)


class CostRecordRead(CostRecordCreate):
    id: str
    created_at: datetime


class CostSummary(BaseSchema):
    total_cost_usd: float
    total_input_tokens: int
    total_output_tokens: int
    total_calls: int
    by_node: dict[str, float] = Field(default_factory=dict)
    by_model: dict[str, float] = Field(default_factory=dict)
    budget_limit_usd: float
    percentage_used: float
    alert_triggered: str | None = None
