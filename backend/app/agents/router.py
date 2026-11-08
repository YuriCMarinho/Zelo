"""Roteador inteligente de entrada para o ponto único de chat do imóvel.

Aplica guardrails rígidos de sanitização e proteção contra prompt injection,
executa triagem determinística de custo zero e recorre ao modelo Qwen3.5-4B
apenas em casos ambíguos.
"""

import re
from typing import Final

from sqlalchemy.orm import Session

from app.core.llm import generate
from app.db.models import MaintenanceTicket
from app.schemas.common import ReportedByRole, RouteDestination, TicketStatus
from app.security.guardrails import validate_untrusted_input

# Termos determinísticos de manutenção
MAINTENANCE_TERMS: Final[set[str]] = {
    "vazamento",
    "vazando",
    "vazar",
    "vaza",
    "torneira",
    "encanador",
    "encanamento",
    "infiltração",
    "infiltracao",
    "esgoto",
    "entupido",
    "entupimento",
    "privada",
    "vaso sanitário",
    "vaso sanitario",
    "chuveiro",
    "ar condicionado",
    "ar-condicionado",
    "arcondicionado",
    "eletricista",
    "elétrica",
    "eletrica",
    "tomada",
    "disjuntor",
    "lâmpada",
    "lampada",
    "fiação",
    "fiacao",
    "apagou",
    "sem energia",
    "sem luz",
    "curto-circuito",
    "curto circuito",
    "quebrado",
    "quebrada",
    "quebrou",
    "quebrando",
    "estragado",
    "estragou",
    "rachadura",
    "defeito",
    "conserto",
    "consertar",
    "reparo",
    "reparar",
    "manutenção",
    "manutencao",
    "pintura",
    "mofo",
    "cheiro de gás",
    "vazando gás",
    "geladeira não gela",
    "fogão quebrado",
    "fechadura emperrada",
    "trinco quebrado",
    "porta emperrada",
}

# Termos determinísticos curtos ou ambíguos com word boundary regex
MAINTENANCE_REGEX: Final[re.Pattern[str]] = re.compile(
    r"\b(luz|gás|gas|cano|vaza|pia|ralo)\b", re.IGNORECASE
)

# Termos determinísticos comerciais
COMMERCIAL_TERMS: Final[set[str]] = {
    "reserva",
    "reservar",
    "diária",
    "diaria",
    "diárias",
    "diarias",
    "preço",
    "preco",
    "preços",
    "precos",
    "valor",
    "valores",
    "quanto custa",
    "check-in",
    "checkin",
    "check in",
    "check-out",
    "checkout",
    "check out",
    "regras",
    "regra",
    "regramento",
    "hospedagem",
    "hospedar",
    "hóspede",
    "hospede",
    "hóspedes",
    "hospedes",
    "datas",
    "disponibilidade",
    "disponível",
    "disponivel",
    "vaga",
    "vagas",
    "wi-fi",
    "wifi",
    "senha da internet",
    "estacionamento",
    "garagem",
    "piscina",
    "churrasqueira",
    "pet",
    "pets",
    "berço",
    "berco",
    "cancelamento",
    "política",
    "politica",
    "fotos",
    "localização",
    "localizacao",
    "como chegar",
}


def _matches_terms(text: str, terms: set[str]) -> bool:
    """Verifica se algum termo está contido no texto normalizado."""
    return any(term in text for term in terms)


async def route_chat_message(
    property_id: str,
    message: str,
    sender_role: ReportedByRole,
    run_id: str,
    db: Session | None = None,
) -> RouteDestination:
    """Roteia a mensagem recebida para o Nó 1 (Comercial) ou Nó 2 (Manutenção).

    Aplica guardrail de entrada contra prompt injection e excesso de tamanho.
    Prioriza regras determinísticas com custo zero e aciona Qwen3.5-4B em casos ambíguos.
    """
    # 1. Guardrail de entrada (validação contra injection e limite de caracteres)
    sanitized = validate_untrusted_input(text=message, role=sender_role.value, run_id=run_id)
    text_lower = sanitized.lower()

    # 2. Regra determinística: mensagens da camareira vão diretamente para manutenção
    if sender_role == ReportedByRole.CLEANER:
        return RouteDestination.MAINTENANCE_NODE2

    # 3. Uma dúvida comercial explícita não muda de assunto por haver chamado aberto.
    is_maintenance = _matches_terms(text_lower, MAINTENANCE_TERMS) or bool(
        MAINTENANCE_REGEX.search(text_lower)
    )
    is_commercial = _matches_terms(text_lower, COMMERCIAL_TERMS)
    explicit_follow_up = re.search(
        r"\b(t[eé]cnico|prestador|chamado|ticket|reparo|conserto)\b", text_lower
    )
    if is_commercial and not is_maintenance and not explicit_follow_up:
        return RouteDestination.COMMERCIAL_NODE1

    # 4. Regra determinística: se o imóvel já tem chamado aberto não resolvido e a mensagem
    # faz menção a acompanhamento, reparo ou técnico, direciona sem custo ao Nó 2
    if db is not None:
        open_tickets = (
            db.query(MaintenanceTicket)
            .filter(
                MaintenanceTicket.property_id == property_id,
                MaintenanceTicket.status != TicketStatus.RESOLVED.value,
            )
            .count()
        )
        if open_tickets > 0:
            follow_up_terms = {
                "técnico",
                "tecnico",
                "visita",
                "chegou",
                "conserto",
                "reparo",
                "chamado",
                "ticket",
                "quando",
                "horário",
                "horario",
                "previsão",
                "previsao",
                "prestador",
                "vaza",
                "problema",
                "ajuda",
                "andamento",
                "status",
                "situação",
                "situacao",
                "arrumou",
                "arrumar",
            }
            if _matches_terms(text_lower, follow_up_terms):
                return RouteDestination.MAINTENANCE_NODE2

    # 5. Regras determinísticas por vocabulário explícito
    if is_maintenance and not is_commercial:
        return RouteDestination.MAINTENANCE_NODE2

    if is_commercial and not is_maintenance:
        return RouteDestination.COMMERCIAL_NODE1

    # 6. Caso ambíguo: chamada ao modelo de roteamento Qwen3.5-4B
    messages = [
        {
            "role": "system",
            "content": (
                "Você é o roteador de atendimento de um imóvel de temporada.\n"
                "Classifique a mensagem estritamente em uma das opções:\n"
                "- commercial_node1 (reserva, preços, regras, check-in)\n"
                "- maintenance_node2 (defeito, quebra, vazamento, manutenção)\n"
                "Responda apenas com 'commercial_node1' ou 'maintenance_node2'."
            ),
        },
        {"role": "user", "content": sanitized},
    ]

    llm_resp = await generate(
        messages=messages,
        model="Qwen/Qwen3.5-4B",
        max_tokens=48,
        run_id=run_id,
        node="router",
        temperature=0.1,
        db=db,
    )

    resp_text = llm_resp.content.lower()
    if (
        "maintenance" in resp_text
        or "manuten" in resp_text
        or "node2" in resp_text
        or "validador" in resp_text
    ):
        return RouteDestination.MAINTENANCE_NODE2

    return RouteDestination.COMMERCIAL_NODE1
