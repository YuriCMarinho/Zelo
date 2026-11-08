from datetime import date, datetime

from pydantic import Field, ValidationInfo, field_validator

from app.schemas.common import BaseSchema, mask_phone


class BookingBase(BaseSchema):
    property_id: str
    guest_name: str = Field(..., min_length=2, max_length=150)
    guest_contact: str = Field(..., description="Telefone ou e-mail de contato")
    start_date: date
    end_date: date
    status: str = Field(
        "confirmed",
        description="pending_approval, confirmed, active, completed, rejected, cancelled",
    )
    total_price: float | None = Field(default=None, description="Valor total da proposta em R$")
    num_guests: int = Field(default=2, ge=1, description="Quantidade de hóspedes")
    rejection_reason: str | None = Field(default=None, description="Motivo de recusa pelo anfitrião")
    session_id: str | None = Field(default=None, description="Sessão anônima do hóspede")
    notes: str | None = None

    @field_validator("end_date")
    @classmethod
    def validate_dates(cls, v: date, info: ValidationInfo) -> date:
        if "start_date" in info.data and v < info.data["start_date"]:
            raise ValueError("A data de término deve ser posterior ou igual à data de início")
        return v


class BookingCreate(BookingBase):
    pass


class BookingApproveRequest(BaseSchema):
    final_price: float | None = Field(
        default=None, gt=0, description="Valor final aprovado pelo anfitrião (opcional)"
    )
    host_notes: str | None = Field(default=None, max_length=500)


class BookingRejectRequest(BaseSchema):
    reason: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Justificativa do anfitrião para recusar a hospedagem",
    )


class BookingRead(BookingBase):
    id: str
    created_at: datetime

    @property
    def masked_contact(self) -> str:
        return mask_phone(self.guest_contact)
