from datetime import date, datetime

from pydantic import Field, ValidationInfo, field_validator

from app.schemas.common import BaseSchema, mask_phone


class BookingBase(BaseSchema):
    property_id: str
    guest_name: str = Field(..., min_length=2, max_length=150)
    guest_contact: str = Field(..., description="Telefone ou e-mail de contato")
    start_date: date
    end_date: date
    status: str = Field("confirmed", description="confirmed, active, completed, cancelled")
    notes: str | None = None

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: date, info: ValidationInfo) -> date:
        if "start_date" in info.data and v < info.data["start_date"]:
            raise ValueError("A data de término deve ser posterior ou igual à data de início")
        return v


class BookingCreate(BookingBase):
    pass


class BookingRead(BookingBase):
    id: str
    created_at: datetime

    @property
    def masked_contact(self) -> str:
        return mask_phone(self.guest_contact)
