"""Contrato da passagem Nó 2 (Validador) → Nó 3 (Resolvedor).

O Nó 2 (S2-T5) depende só deste contrato; o Nó 3 (S2-T6) fornece a implementação.
Assim as duas tasks rodam em paralelo e se integram sem tocar nos arquivos uma da outra.
"""

from typing import Protocol, runtime_checkable

from pydantic import Field

from app.schemas.common import BaseSchema, NonBlankStr


class ResolutionRequest(BaseSchema):
    """Pedido para o Nó 3 iniciar a resolução de um ticket já persistido no banco.

    O imóvel e os demais dados vêm do próprio ticket (fonte única), não do pedido.
    """

    ticket_id: NonBlankStr
    run_id: NonBlankStr  # mesmo run_id do ticket (auditoria ponta a ponta)


@runtime_checkable
class ResolverStarter(Protocol):
    """Porta de entrada do Nó 3. Deve ser idempotente por ticket_id."""

    def start_resolution(self, request: ResolutionRequest) -> None: ...


class ProviderQuoteReply(BaseSchema):
    """Resposta de um prestador a um pedido de orçamento (canal simulado/allowlist)."""

    amount: float = Field(..., ge=0, le=1_000_000)
    description: str | None = Field(None, max_length=500)
    proposed_availability: str | None = Field(None, max_length=200)


class ProviderDateReply(BaseSchema):
    """Devolutiva do dia: o prestador escolhido aceita ou recusa a data proposta."""

    accepted: bool
    message: str | None = Field(None, max_length=500)
