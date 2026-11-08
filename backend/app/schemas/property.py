from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema


class PropertyBase(BaseSchema):
    name: str = Field(..., min_length=2, max_length=200, description="Nome de exibição do imóvel")
    description: str = Field(..., description="Descrição completa do imóvel estilo Airbnb")
    address: str = Field(..., description="Endereço do imóvel")
    city: str = Field(..., description="Cidade")
    state: str = Field(..., max_length=2, description="UF do estado (ex: RJ, SP)")
    nightly_rate: float = Field(default=350.0, gt=0, description="Valor da diária em R$")
    rules_faq: str | None = Field(None, description="Regras da casa e FAQ do imóvel")


class PropertyCreate(PropertyBase):
    pass


class PropertyRead(PropertyBase):
    id: str
    created_at: datetime
    updated_at: datetime
