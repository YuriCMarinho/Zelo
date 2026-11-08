"""Reproduz respostas reais gravadas, limitadas aos cenários documentados da demo."""

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.security.masking import mask_pii


class RecordedDemoError(ValueError):
    """Gravação ausente, incompatível ou cenário não suportado (nunca recorre à API)."""


@lru_cache(maxsize=1)
def recordings() -> dict[str, Any]:
    path = Path(__file__).with_name("recordings.json")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RecordedDemoError("Arquivo de respostas gravadas indisponível.") from exc
    if data.get("version") != 1 or not isinstance(data.get("responses"), dict):
        raise RecordedDemoError("Formato de gravações incompatível.")
    return dict(data["responses"])


def replay(node: str, model: str, messages: list[dict[str, str]]) -> str:
    user = next((item["content"] for item in reversed(messages) if item["role"] == "user"), "")
    key = node
    if node == "router":
        maintenance = re.search(
            r"defeito|quebr|vaza|consert|manuten|sem energia|não esquenta", user, re.I
        )
        key = "router.maintenance" if maintenance else "router.commercial"
    elif node == "commercial_node1":
        greeting = re.fullmatch(
            r"[\s!.,]*(oi|olá|ola|bom dia|boa tarde|boa noite)[\s!.,]*", user, re.I
        )
        key = "commercial.greeting" if greeting else "commercial.unavailable"
    entry = recordings().get(key)
    if not isinstance(entry, dict) or entry.get("model") != model:
        raise RecordedDemoError(f"Sem gravação para o cenário '{key}' com o modelo solicitado.")
    content = entry.get("content")
    if not isinstance(content, str) or not content.strip():
        raise RecordedDemoError(f"Gravação vazia para '{key}'.")
    if node == "resolver_notify_tenant":
        service, separator, scheduled = user.removeprefix("Serviço: ").rpartition(". Data/Hora: ")
        if not separator:
            raise RecordedDemoError("Aviso gravado requer serviço e data confirmada.")
        content = content.replace("{{service}}", mask_pii(service))
        content = content.replace("{{scheduled_date}}", scheduled.rstrip("."))
    return content
