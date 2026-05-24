"""
Script para deletar eventos [RL] (Rocket League) do calendario.
"""

import sys
from calendar_manager import CalendarManager
from logger import setup_logger

PREFIX = "[RL] "
LABEL = "Rocket League"


def main():
    logger = setup_logger("delete_rl")
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
