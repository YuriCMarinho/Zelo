"""Módulo de logging estruturado com filtro automático de mascaramento de PII.

Garante que nenhuma informação pessoal sensível seja gravada em stdout, stderr ou arquivos.
"""

import logging
import sys

from app.core.config import settings
from app.security.masking import mask_dict_pii, mask_pii


class PIIMaskingFilter(logging.Filter):
    """Filtro de log que intercepta mensagens e argumentos, aplicando mask_pii."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = mask_pii(record.msg)

        if record.args:
            if isinstance(record.args, dict):
                record.args = mask_dict_pii(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(mask_dict_pii(arg) for arg in record.args)

        return True


def setup_logger(name: str = "smartrepair") -> logging.Logger:
    """Configura e retorna um logger padronizado com mascaramento de PII."""
    logger_instance = logging.getLogger(name)
    logger_instance.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    # Evita duplicação de handlers se já configurado
    if not logger_instance.handlers:
        handler = logging.StreamHandler(sys.stdout)
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s (run_id=%(run_id)s): %(message)s",
            defaults={"run_id": "none"},
        )
        handler.setFormatter(formatter)
        handler.addFilter(PIIMaskingFilter())
        logger_instance.addHandler(handler)
        logger_instance.propagate = False
    else:
        # Garante que os handlers existentes tenham o filtro de PII
        for existing_handler in logger_instance.handlers:
            if not any(isinstance(f, PIIMaskingFilter) for f in existing_handler.filters):
                existing_handler.addFilter(PIIMaskingFilter())

    return logger_instance


logger = setup_logger()


def get_logger(name: str = "smartrepair") -> logging.Logger:
    """Obtém ou cria um logger configurado com filtro de PII."""
    return logging.getLogger(name)
