from pydantic import Field

from app.schemas.common import BaseSchema, ReportedByRole, RouteDestination


class ChatMessageInput(BaseSchema):
    property_id: str = Field(..., min_length=1, description="ID do imóvel")
    message: str = Field(..., min_length=1, description="Texto da mensagem enviada")
    sender_role: ReportedByRole = Field(
        default=ReportedByRole.TENANT,
        description="tenant ou cleaner",
    )
    run_id: str | None = Field(
        None,
        description="run_id opcional; se não informado, será gerado automaticamente",
    )


class ChatMessageOutput(BaseSchema):
    run_id: str
    property_id: str
    route_destination: RouteDestination
    response_text: str
    ticket_id: str | None = None
    suggested_actions: list[str] = Field(default_factory=list)
