import os
from icalendar import Calendar

CALENDAR_FILENAME = "calendar.ics"
SOURCE_MARKER = "X-SETT-SOURCE:TIPSGG"

def load_calendar(path: str) -> Calendar:
    if os.path.exists(path):
        try:
            with open(path, "rb") as f:
                return Calendar.from_ical(f.read())
        except Exception as e:
            print(f"❌ Erro ao ler {path}: {e}")
            return None
    return None

def save_calendar(cal: Calendar, path: str):
    try:
        with open(path, "wb") as f:
            f.write(cal.to_ical())
        print(f"✅ Salvo: {path}")
    except Exception as e:
        print(f"❌ Erro ao salvar: {e}")

def delete_cs2_events(cal: Calendar) -> int:
    to_remove = []
    for component in list(cal.walk('VEVENT')):
        summary = str(component.get('summary', ''))
        if '[CS2]' in summary:
            to_remove.append(component)

    for comp in to_remove:
        cal.subcomponents.remove(comp)

    return len(to_remove)

# Executa
print("🚀 Deletando eventos [CS2]...")
cal = load_calendar(CALENDAR_FILENAME)

if cal:
    removed = delete_cs2_events(cal)
    print(f"🗑️  Removidos {removed} eventos [CS2]")
    save_calendar(cal, CALENDAR_FILENAME)
else:
    print("❌ Calendário não encontrado")
