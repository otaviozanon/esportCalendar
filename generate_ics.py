from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from ics import Calendar, Event
from datetime import datetime, timedelta
import time

# Lista de times brasileiros
BRAZILIAN_TEAMS = ["FURIA", "paiN", "LOUD", "MIBR", "INTZ", "VIVO KEYD"]

# Configuração do Chrome headless
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

try:
    url = "https://draft5.gg/proximas-partidas"
    print(f"🔹 Acessando URL: {url}")
    driver.get(url)

    # Espera simples: até 15s procurando por cards
    cards_elements = []
    for _ in range(15):
        cards_elements = driver.find_elements(By.CSS_SELECTOR, "div[class*='MatchCardSimple__Match']")
        if cards_elements:
            break
        time.sleep(1)
    else:
        print("⚠️ Nenhum card encontrado após 15 segundos")

    calendar = Calendar()
    total_found = 0

    for card_el in cards_elements:
        try:
            # Pega os times
            teams_divs = card_el.find_elements(By.CSS_SELECTOR, "div[class*='MatchCardSimple__MatchTeam']")
            if len(teams_divs) != 2:
                continue

            team1 = teams_divs[0].find_element(By.TAG_NAME, "span").text.strip()
            team2 = teams_divs[1].find_element(By.TAG_NAME, "span").text.strip()

            if not any(team in [team1, team2] for team in BRAZILIAN_TEAMS):
                continue

            # Pega o horário via JavaScript (renderizado dinamicamente)
            hour_min = driver.execute_script(
                "return arguments[0].querySelector('small[class*=\"MatchCardSimple__MatchTime\"] span')?.innerText;", 
                card_el
            )

            if not hour_min:
                print(f"⚠️ Horário não encontrado para o jogo: {team1} vs {team2}")
                continue

            # Usa data atual como referência (pode ser ajustado para a data real do jogo)
            today_str = datetime.now().strftime("%d/%m/%Y")
            event_time = datetime.strptime(f"{today_str} {hour_min}", "%d/%m/%Y %H:%M")

            # Cria evento no calendário
            e = Event()
            e.name = f"{team1} vs {team2}"
            e.begin = event_time
            e.duration = timedelta(hours=1)
            calendar.events.add(e)
            total_found += 1
            print(f"✅ Jogo adicionado: {e.name} - {e.begin}")

        except Exception as ex:
            print(f"⚠️ Erro ao processar card: {ex}")

finally:
    driver.quit()

# Gera o arquivo ICS
with open("calendar.ics", "w", encoding="utf-8") as f:
    f.writelines(calendar)

print(f"🔹 calendar.ics gerado com sucesso! Total de jogos adicionados: {total_found}")
