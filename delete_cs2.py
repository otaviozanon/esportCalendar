"""
Script para deletar eventos [CS2] do calendário.
Carrega, processa, salva com logging estruturado.
"""

import os
import sys
from datetime import datetime
from typing import Optional
from icalendar import Calendar
import pytz

# -------------------- Configurações --------------------
CALENDAR_FILENAME = "calendar.ics"
SOURCE_MARKER = "X-SETT-SOURCE:TIPSGG"
BR_TZ = pytz.timezone("America/Sao_Paulo")
GAME_PREFIX = "[CS2]"


# -------------------- Logging --------------------
def log(msg: str):
    """Log com timestamp."""
    now = datetime.now(BR_TZ).strftime("%H:%M:%S")
    print(f"[{now}] {msg}")


# -------------------- Calendar Operations --------------------
def load_calendar(path: str) -> Optional[Calendar]:
    """
    Carrega calendário do arquivo.

    Args:
        path: Caminho do arquivo .ics

    Returns:
        Calendar ou None se falhar
    """
    if not os.path.exists(path):
        log(f"❌ Arquivo não encontrado: {path}")
        return None

    try:
        with open(path, "rb") as f:
            cal = Calendar.from_ical(f.read())
        log(f"✅ Calendário carregado: {path}")
        return cal
    except Exception as e:
        log(f"❌ Erro ao ler {path}: {type(e).__name__}: {e}")
        return None


def save_calendar(cal: Calendar, path: str) -> bool:
    """
    Salva calendário em arquivo.

    Args:
        cal: Objeto Calendar
        path: Caminho de destino

    Returns:
        True se sucesso, False se falhar
    """
    try:
        with open(path, "wb") as f:
            f.write(cal.to_ical())
        log(f"✅ Calendário salvo: {path}")
        return True
    except Exception as e:
        log(f"❌ Erro ao salvar {path}: {type(e).__name__}: {e}")
        return False


def count_events(cal: Calendar) -> int:
    """Conta total de eventos VEVENT no calendário."""
    return len(list(cal.walk('VEVENT')))


def delete_cs2_events(cal: Calendar) -> dict:
    """
    Remove eventos com prefixo [CS2].

    Args:
        cal: Objeto Calendar

    Returns:
        Dict com estatísticas: {removed, total_before, total_after}
    """
    total_before = count_events(cal)
    to_remove = []

    # Identifica eventos CS2
    for component in list(cal.walk('VEVENT')):
        summary = str(component.get('summary', ''))
        if GAME_PREFIX in summary:
            to_remove.append({
                'component': component,
                'summary': summary
            })

    # Remove eventos
    for item in to_remove:
        cal.subcomponents.remove(item['component'])

    total_after = count_events(cal)

    return {
        'removed': len(to_remove),
        'total_before': total_before,
        'total_after': total_after,
        'events': to_remove
    }


# -------------------- Execução --------------------
def main():
    """Executa limpeza de eventos CS2."""
    log("=" * 60)
    log("🚀 INICIANDO LIMPEZA DE EVENTOS")
    log("=" * 60)

    # Carrega calendário
    log(f"📂 Carregando: {CALENDAR_FILENAME}")
    cal = load_calendar(CALENDAR_FILENAME)

    if not cal:
        log("❌ Falha ao carregar calendário. Abortando.")
        return False

    # Conta eventos iniciais
    total_initial = count_events(cal)
    log(f"📊 Total de eventos: {total_initial}")

    # Deleta eventos CS2
    log(f"🔍 Procurando eventos {GAME_PREFIX}...")
    stats = delete_cs2_events(cal)

    # Exibe resultados
    log("-" * 60)
    if stats['removed'] > 0:
        log(f"🗑️  REMOVIDOS ( {stats['removed']} ) | ANTES ( {stats['total_before']} ) | DEPOIS ( {stats['total_after']} )")

        # Lista eventos removidos
        for event in stats['events']:
            log(f"  ✓ {event['summary']}")
    else:
        log(f"ℹ️  Nenhum evento {GAME_PREFIX} encontrado")

    log("-" * 60)

    # Salva calendário
    log(f"💾 Salvando {CALENDAR_FILENAME}...")
    if not save_calendar(cal, CALENDAR_FILENAME):
        log("❌ Falha ao salvar. Abortando.")
        return False

    # Resumo final
    log(f"✅ Concluído | Removidos: {stats['removed']} | Restantes: {stats['total_after']}")
    log("=" * 60)
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        log("\n⚠️  Interrompido pelo usuário")
        sys.exit(1)
    except Exception as e:
        log(f"❌ ERRO NÃO TRATADO: {type(e).__name__}: {e}")
        import traceback
        log(f"📍 Stack trace:\n{traceback.format_exc()}")
        sys.exit(1)
