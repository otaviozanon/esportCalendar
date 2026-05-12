"""
Script para deletar eventos [CS2] do calendário.
Versão Profissional utilizando core.py.
"""

import sys
from core import CalendarManager, setup_logger

def main():
    logger = setup_logger("delete_cs2")
    logger.info("=" * 60)
    logger.info("🚀 INICIANDO LIMPEZA DE EVENTOS CS2")
    logger.info("=" * 60)

    cm = CalendarManager()
    
    prefix = "[CS2]"
    logger.info(f"🔍 Procurando eventos com prefixo '{prefix}'...")
    
    removed = cm.remove_events_by_prefix(prefix)
    
    if removed > 0:
        logger.info(f"🗑️  REMOVIDOS: {removed} eventos")
        if cm.save():
            logger.info("💾 Calendário atualizado com sucesso.")
        else:
            logger.error("❌ Falha ao salvar o calendário.")
            return False
    else:
        logger.info(f"ℹ️  Nenhum evento '{prefix}' encontrado.")

    logger.info("=" * 60)
    logger.info("✅ CONCLUÍDO")
    logger.info("=" * 60)
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
