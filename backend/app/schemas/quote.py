from datetime import datetime

from pydantic import Field, field_validator

from app.schemas.common import BaseSchema, QuoteStatus


class QuoteBase(BaseSchema):
    ticket_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1)
    provider_id: str = Field(..., min_length=1)
    amount: float | None = Field(None, ge=0)
    description: str | None = None
    proposed_availability: str | None = None
    status: QuoteStatus = Field(default=QuoteStatus.REQUESTED)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("run_id é obrigatório")
        return v.strip()


class QuoteCreateRequest(QuoteBase):
    pass


class QuoteResponseCreate(BaseSchema):
    run_id: str = Field(..., min_length=1)
    amount: float = Field(..., ge=0)
    description: str | None = None
    proposed_availability: str | None = None


class QuoteRead(QuoteBase):
    id: str
    created_at: datetime
