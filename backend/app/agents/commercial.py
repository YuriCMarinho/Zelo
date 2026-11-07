"""Nó 1: Agente Comercial (Fluxo A — Aquisição e Atendimento).

Atende dúvidas sobre o imóvel com tom caloroso e hospitaleiro (estilo Superhost do Airbnb).
Identifica intenção de reserva, valida disponibilidade na agenda (evitando conflito de datas)
e persiste o Booking confirmado no banco de dados.
"""

import re
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.llm import generate
from app.db.models import Booking, Property
from app.schemas.chat import ChatMessageOutput
from app.schemas.common import RouteDestination

RESERVATION_INTENT_PATTERN = re.compile(
    r"\b(reserva|reservar|alugar|fechar estadia|confirmar reserva|quero ficar)\b",
    re.IGNORECASE,
)

DATE_ISO_PATTERN = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
DATE_BR_PATTERN = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")


def _extract_dates_from_message(message: str) -> tuple[date, date] | None:
    """Extrai intervalo de datas (início e término) da mensagem, se presente."""
    iso_matches = DATE_ISO_PATTERN.findall(message)
    if len(iso_matches) >= 2:
        try:
            d1 = datetime.strptime(iso_matches[0], "%Y-%m-%d").date()
            d2 = datetime.strptime(iso_matches[1], "%Y-%m-%d").date()
            return (d1, d2) if d1 <= d2 else (d2, d1)
        except ValueError:
            pass

    br_matches = DATE_BR_PATTERN.findall(message)
    if len(br_matches) >= 2:
        try:
            d1 = datetime.strptime(br_matches[0], "%d/%m/%Y").date()
            d2 = datetime.strptime(br_matches[1], "%d/%m/%Y").date()
            return (d1, d2) if d1 <= d2 else (d2, d1)
        except ValueError:
            pass

    return None


async def handle_commercial_message(
    prop: Property,
    message: str,
    run_id: str,
    db: Session | None = None,
) -> ChatMessageOutput:
    """Atende mensagens comerciais com tom acolhedor e processa intenção de reserva.

    Utiliza Qwen3.5-9B com max_tokens=256 para respostas conversacionais.
    Caso a mensagem expresse intenção de reserva, checa disponibilidade e persiste o Booking.
    """
    has_reservation_intent = bool(RESERVATION_INTENT_PATTERN.search(message))

    # Fluxo de Confirmação de Reserva
    if has_reservation_intent and db is not None:
        extracted = _extract_dates_from_message(message)
        if extracted is not None:
            cand_start, cand_end = extracted
        else:
            # Janela de reserva simulada padrão (inicia em 14 dias com duração de 3 noites)
            cand_start = date.today() + timedelta(days=14)
            cand_end = cand_start + timedelta(days=3)

        # Checa conflito de sobreposição na agenda do imóvel
        conflict = (
            db.query(Booking)
            .filter(
                Booking.property_id == prop.id,
                Booking.status.in_(["confirmed", "active"]),
                Booking.start_date < cand_end,
                Booking.end_date > cand_start,
            )
            .first()
        )

        if conflict:
            conflict_msg = (
                f"Olá! Que ótimo seu interesse no imóvel '{prop.name}'. "
                f"Verifiquei em nosso calendário que o período de "
                f"{cand_start.strftime('%d/%m/%Y')} a {cand_end.strftime('%d/%m/%Y')} "
                f"já possui uma reserva confirmada. "
                f"Que tal escolhermos outras datas para que você possa aproveitar essa estadia?"
            )
            return ChatMessageOutput(
                run_id=run_id,
                property_id=prop.id,
                route_destination=RouteDestination.COMMERCIAL_NODE1,
                response_text=conflict_msg,
                suggested_actions=[
                    "Escolher outras datas",
                    "Consultar calendário",
                    "Falar com o anfitrião",
                ],
            )

        # Criação e persistência do Booking confirmado
        new_booking = Booking(
            property_id=prop.id,
            guest_name="Hóspede Confirmado",
            guest_contact="(11) 98888-7777",
            start_date=cand_start,
            end_date=cand_end,
            status="confirmed",
            notes=f"Reserva confirmada via Nó 1 Comercial (run_id: {run_id})",
        )
        db.add(new_booking)
        db.commit()
        db.refresh(new_booking)

        confirmation_msg = (
            f"Parabéns! Sua reserva para o imóvel '{prop.name}' foi confirmada com sucesso! "
            f"Período confirmado: de {cand_start.strftime('%d/%m/%Y')} a "
            f"{cand_end.strftime('%d/%m/%Y')}. "
            f"Estamos muito felizes em receber você. Em breve enviaremos todas as instruções "
            f"de check-in e comodidades para tornar sua viagem inesquecível!"
        )
        return ChatMessageOutput(
            run_id=run_id,
            property_id=prop.id,
            route_destination=RouteDestination.COMMERCIAL_NODE1,
            response_text=confirmation_msg,
            suggested_actions=[
                "Ver detalhes da reserva",
                "Consultar regras de check-in",
                "Como chegar ao imóvel",
            ],
        )

    # Fluxo Conversacional de Atendimento Comercial
    faq_context = prop.rules_faq or "Regras da casa: silêncio após as 22h, não fumar no interior."
    system_prompt = (
        f"Você é o anfitrião caloroso, atencioso e prestativo do imóvel '{prop.name}' "
        f"localizado em {prop.city}/{prop.state} ({prop.address}).\n"
        f"Descrição do imóvel: {prop.description}\n"
        f"Regras e comodidades: {faq_context}\n"
        "Seu tom é cordial, amigável e acolhedor (estilo Superhost do Airbnb). "
        "Responda às dúvidas com clareza, hospitalidade e convide o hóspede a se hospedar."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message},
    ]

    llm_resp = await generate(
        messages=messages,
        model="Qwen/Qwen3.5-9B",
        max_tokens=256,
        run_id=run_id,
        node="commercial_node1",
        temperature=0.3,
        db=db,
    )

    return ChatMessageOutput(
        run_id=run_id,
        property_id=prop.id,
        route_destination=RouteDestination.COMMERCIAL_NODE1,
        response_text=llm_resp.content,
        suggested_actions=[
            "Fazer uma reserva",
            "Consultar regras de check-in",
            "Tirar dúvidas sobre a região",
        ],
    )
