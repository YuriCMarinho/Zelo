"""Contrato da passagem Nó 2 (Validador) → Nó 3 (Resolvedor).

O Nó 2 (S2-T5) depende só deste contrato; o Nó 3 (S2-T6) fornece a implementação.
Assim as duas tasks rodam em paralelo e se integram sem tocar nos arquivos uma da outra.
"""

from typing import Protocol, runtime_checkable

from pydantic import Field

from app.schemas.common import BaseSchema


class ResolutionRequest(BaseSchema):
    """Pedido para o Nó 3 iniciar a resolução de um ticket já persistido no banco."""

    ticket_id: str = Field(..., min_length=1)
    property_id: str = Field(..., min_length=1)
    run_id: str = Field(..., min_length=1, description="Mesmo run_id do ticket (auditoria)")


@runtime_checkable
class ResolverStarter(Protocol):
    """Porta de entrada do Nó 3. Deve ser idempotente por ticket_id."""

    def start_resolution(self, request: ResolutionRequest) -> None: ...
