"""Nó 2: Agente Validador / Triagem de Manutenção (Início do Fluxo C).

Avalia relatos de inquilino ou camareira sobre problemas físicos no imóvel.
Se o relato for vago ou incompleto, solicita esclarecimento empático sem abrir chamado.
Se houver informações suficientes, classifica categoria e urgência com Qwen3.5-4B
e persiste o MaintenanceTicket estruturado no PostgreSQL com status 'open'.
"""

import re
from typing import Final

from sqlalchemy.orm import Session

from app.core.llm import generate
from app.db.models import MaintenanceTicket, Property
from app.schemas.common import ProviderCategory, ReportedByRole, TicketUrgency

ROOMS: Final[set[str]] = {
    "banheiro",
    "suíte",
    "suite",
    "lavabo",
    "cozinha",
    "sala",
    "quarto",
    "dormitório",
    "dormitorio",
    "varanda",
    "sacada",
    "área de serviço",
    "area de servico",
    "lavanderia",
    "garagem",
    "corredor",
    "hall",
    "piscina",
    "jardim",
    "fachada",
    "telhado",
    "área externa",
    "area externa",
}

ITEMS: Final[set[str]] = {
    "torneira",
    "cano",
    "pia",
    "chuveiro",
    "privada",
    "vaso sanitário",
    "vaso sanitario",
    "vaso",
    "infiltração",
    "infiltracao",
    "ralo",
    "esgoto",
    "luz",
    "lâmpada",
    "lampada",
    "tomada",
    "disjuntor",
    "fiação",
    "fiacao",
    "interruptor",
    "ar condicionado",
    "ar-condicionado",
    "arcondicionado",
    "geladeira",
    "fogão",
    "fogao",
    "microondas",
    "micro-ondas",
    "forno",
    "fechadura",
    "maçaneta",
    "macaneta",
    "porta",
    "janela",
    "parede",
    "teto",
    "piso",
    "pintura",
    "mofo",
    "ventilador",
    "televisão",
    "televisao",
    "tv",
    "vazamento",
    "gás",
    "gas",
}

URGENT_TERMS: Final[set[str]] = {
    "vazamento",
    "vazando",
    "vazar",
    "vaza",
    "infiltração",
    "infiltracao",
    "inundação",
    "inundacao",
    "jorrando",
    "cano estourado",
    "esgoto",
    "sem luz",
    "apagão",
    "apagao",
    "curto-circuito",
    "curto circuito",
    "faísca",
    "faisca",
    "choque",
    "gás",
    "gas",
    "cheiro de gás",
    "fechadura emperrada",
    "trancado para fora",
    "segurança",
    "seguranca",
}


def _is_vague_report(text: str) -> bool:
    """Identifica se o relato é excessivamente vago ou incompleto."""
    cleaned = re.sub(r"[^\w\s-]", " ", text.lower())
    words = [w for w in cleaned.split() if len(w) > 1]

    has_room = any(room in text.lower() for room in ROOMS)
    has_item = any(item in text.lower() for item in ITEMS)

    # Menos de 4 palavras sem cômodo nem item, ou ausência total de cômodo e item
    if len(words) < 4 and not (has_room or has_item):
        return True

    return not has_room and not has_item


def _detect_category(text_lower: str) -> ProviderCategory:
    """Classifica a categoria de serviço com base no problema relatado."""
    plumber_terms = {
        "vaza",
        "torneira",
        "cano",
        "pia",
        "ralo",
        "esgoto",
        "privada",
        "vaso",
        "infiltra",
        "chuveiro",
        "água",
        "agua",
    }
    if any(t in text_lower for t in plumber_terms):
        return ProviderCategory.PLUMBER

    electrician_terms = {
        "luz",
        "lâmpada",
        "lampada",
        "tomada",
        "disjuntor",
        "fiação",
        "fiacao",
        "eletric",
        "energia",
        "curto",
        "faísca",
        "faisca",
        "choque",
    }
    if any(t in text_lower for t in electrician_terms):
        return ProviderCategory.ELECTRICIAN

    painter_terms = {"pintura", "parede", "mofo", "descascando", "tinta"}
    if any(t in text_lower for t in painter_terms):
        return ProviderCategory.PAINTER

    organizer_terms = {"organiza", "faxina", "limpeza pesada", "arrumação", "arrumacao"}
    if any(t in text_lower for t in organizer_terms):
        return ProviderCategory.ORGANIZER

    return ProviderCategory.GENERAL_MAINTENANCE


def _detect_urgency(text_lower: str) -> TicketUrgency:
    """Determina a urgência do chamado."""
    if any(term in text_lower for term in URGENT_TERMS):
        return TicketUrgency.URGENT
    return TicketUrgency.NORMAL


def _detect_location(text_lower: str) -> str:
    """Detecta o cômodo ou local indicado no relato."""
    for room in [
        "banheiro da suíte",
        "banheiro social",
        "suíte",
        "suite",
        "banheiro",
        "cozinha",
        "área de serviço",
        "area de servico",
        "lavanderia",
        "sala de estar",
        "sala",
        "quarto",
        "varanda",
        "sacada",
        "garagem",
        "corredor",
        "piscina",
    ]:
        if room in text_lower:
            return room.capitalize()
    return "Imóvel (Geral)"


async def handle_maintenance_message(
    prop: Property,
    message: str,
    sender_role: ReportedByRole,
    run_id: str,
    db: Session,
    history: list[dict[str, str]] | None = None,
) -> tuple[str, str | None]:
    """Processa relatos de manutenção no Nó 2.

    Se o relato for vago ou incompleto, formula esclarecimento empático sem abrir ticket.
    Se suficiente (ou complementado em conversa multi-turn), classifica com Qwen3.5-4B,
    persiste o MaintenanceTicket e retorna confirmação com orientação de segurança se aplicável.
    """
    effective_message = message.strip()
    if history:
        last_assistant = next(
            (h["content"].lower() for h in reversed(history) if h.get("role") == "assistant"),
            "",
        )
        prev_user = next(
            (h["content"] for h in reversed(history) if h.get("role") == "user"),
            "",
        )
        if ("qual item" in last_assistant or "qual cômodo" in last_assistant) and prev_user:
            effective_message = f"{prev_user.strip()} - {effective_message}"

    text_lower = effective_message.lower()

    # 1. Verificação de relato vago ou incompleto
    if _is_vague_report(effective_message):
        clarification_msg = (
            "Sentimos muito pelo inconveniente com o imóvel! Para que possamos acionar "
            "o especialista correto e resolver a questão com agilidade, você poderia "
            "nos detalhar qual item está com defeito e em qual cômodo ele se encontra "
            "(por exemplo: torneira na pia da cozinha ou chuveiro no banheiro)?"
        )
        return (clarification_msg, None)

    # 2. Classificação de atributos do chamado
    category = _detect_category(text_lower)
    urgency = _detect_urgency(text_lower)
    location = _detect_location(text_lower)
    clean_description = effective_message

    # 3. Chamada ao modelo validador Qwen3.5-4B
    system_prompt = (
        f"Você é o agente validador de manutenção do imóvel '{prop.name}'.\n"
        f"Analise o relato do papel '{sender_role.value}'.\n"
        f"Local identificado: {location}. Categoria: {category.value}. "
        f"Urgência: {urgency.value}.\n"
        "Confirme os dados técnicos de triagem com precisão."
    )
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": effective_message},
    ]

    await generate(
        messages=messages,
        model="Qwen/Qwen3.5-4B",
        max_tokens=256,
        run_id=run_id,
        node="validator_node2",
        temperature=0.1,
        db=db,
    )

    # 4. Criação e persistência do MaintenanceTicket com status 'open'
    ticket = MaintenanceTicket(
        run_id=run_id,
        property_id=prop.id,
        reported_by_role=sender_role.value,
        category=category.value,
        urgency=urgency.value,
        location_in_property=location,
        description=clean_description,
        status="open",
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)

    urgency_label = "URGENTE" if urgency == TicketUrgency.URGENT else "NORMAL"
    safety_note = ""
    if any(k in text_lower for k in ("faísca", "faisca", "choque", "curto")):
        safety_note = " Por segurança, recomendamos não utilizar o ponto elétrico até a chegada do profissional."
    elif any(k in text_lower for k in ("gás", "gas")):
        safety_note = " Por segurança, feche o registro de gás e mantenha o ambiente ventilado."

    confirmation_msg = (
        f"Compreendido e registrado com sucesso! Abrimos o chamado de manutenção "
        f"#{ticket.id[:8]} com nível de urgência '{urgency_label}' para {location}.{safety_note} "
        f"Nossa plataforma já está iniciando a cotação com prestadores homologados "
        f"para resolver o problema o mais breve possível."
    )

    return (confirmation_msg, ticket.id)
