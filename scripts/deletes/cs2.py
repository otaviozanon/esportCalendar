"""
Script para deletar eventos [CS2] do calendario.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calendar_manager import CalendarManager
from logger import setup_logger

PREFIX = "[CS2] "
LABEL = "CS2"


def main():
    logger = setup_logger("delete_cs2")
    logger.info("=" * 60)
    logger.info("\U0001f680 INICIANDO LIMPEZA DE EVENTOS %s" % LABEL)
    logger.info("=" * 60)

    cm = CalendarManager()
    logger.info("\U0001f50d Procurando eventos com prefixo '%s'..." % PREFIX)

    removed = cm.remove_events_by_prefix(PREFIX)

    if removed > 0:
        logger.info("\U0001f5d1\ufe0f  REMOVIDOS: %d eventos" % removed)
        if cm.save():
            logger.info("\U0001f4be Calendario atualizado com sucesso.")
        else:
            logger.error("\u274c Falha ao salvar o calendario.")
            return False
    else:
        logger.info("\u2139\ufe0f  Nenhum evento '%s' encontrado." % PREFIX)

    logger.info("=" * 60)
    logger.info("\u2705 CONCLUIDO")
    logger.info("=" * 60)
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
