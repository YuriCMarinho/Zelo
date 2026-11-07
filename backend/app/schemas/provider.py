from datetime import datetime

from pydantic import Field

from app.schemas.common import BaseSchema, ProviderCategory, mask_phone


class ProviderBase(BaseSchema):
    name: str = Field(..., min_length=2, max_length=150)
    category: ProviderCategory
    region: str = Field(..., max_length=100)
    phone: str = Field(..., max_length=30)
    is_validated: bool = Field(default=False)
    rating: float | None = Field(default=5.0, ge=1.0, le=5.0)
    source: str = Field(default="fixture")


class ProviderCreate(ProviderBase):
    pass


class ProviderRead(ProviderBase):
    id: str
    created_at: datetime

    @property
    def masked_phone(self) -> str:
        return mask_phone(self.phone)
