"""
Configuracao de logging centralizada.
"""

import logging


def setup_logger(name: str = "esport_calendar") -> logging.Logger:
    """Configura e retorna logger com timestamp HH:MM:SS e output em stdout."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        "[%(asctime)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    return logger
