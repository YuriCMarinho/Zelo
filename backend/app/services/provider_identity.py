import hashlib
import re
import unicodedata
from typing import Any


def normalized_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    return "55" + digits if len(digits) in (10, 11) else digits


def provider_identity(category: str, region: str, phone: str) -> str:
    location = unicodedata.normalize("NFKD", region).encode("ascii", "ignore").decode().casefold()
    location = re.sub(r"\s*,\s*", ",", " ".join(location.split()))
    identity = f"{getattr(category, 'value', category)}|{location}|{normalized_phone(phone)}"
    return hashlib.sha256(identity.encode()).hexdigest()


def identity_default(context: Any) -> str:
    values = context.get_current_parameters()
    return provider_identity(values["category"], values["region"], values["phone"])
