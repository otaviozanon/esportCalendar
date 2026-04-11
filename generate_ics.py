from scrapling import Scraper
from datetime import date

# Configuração básica
game_base_path = "https://tips.gg/csgo/matches/"
target_date = date.today()
date_str = target_date.strftime("%d-%m-%Y")
test_url = f"{game_base_path}{date_str}/"

print(f"🔍 Testando Scrapling em: {test_url}\n")

# Criar scraper
scraper = Scraper()

try:
    # Fazer a requisição
    print("⏳ Carregando página...")
    response = scraper.fetch(test_url)

    print(f"✅ Status: {response.status_code}")
    print(f"📄 Tamanho do conteúdo: {len(response.text)} caracteres\n")

    # Tentar encontrar scripts JSON-LD
    print("🔎 Procurando scripts JSON-LD...\n")

    # Método 1: Buscar direto no HTML
    html = response.text
    import re
    json_ld_scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)

    print(f"📊 Scripts JSON-LD encontrados: {len(json_ld_scripts)}\n")

    if json_ld_scripts:
        import json
        for i, script in enumerate(json_ld_scripts[:3], 1):  # Mostrar apenas os 3 primeiros
            try:
                data = json.loads(script)
                print(f"--- Script {i} ---")
                print(f"Tipo: {data.get('@type', 'N/A')}")
                print(f"Chaves principais: {list(data.keys())}")

                if data.get('@type') == 'SportsEvent':
                    print(f"✅ É um SportsEvent!")
                    print(f"  - startDate: {data.get('startDate', 'N/A')}")
                    print(f"  - description: {data.get('description', 'N/A')[:50]}...")
                    competitors = data.get('competitor', [])
                    print(f"  - competitors: {len(competitors)}")
                    if competitors:
                        print(f"    • {competitors[0].get('name', 'N/A')} vs {competitors[1].get('name', 'N/A') if len(competitors) > 1 else 'N/A'}")
                print()
            except json.JSONDecodeError as e:
                print(f"❌ Erro ao decodificar script {i}: {e}\n")
    else:
        print("⚠️ Nenhum script JSON-LD encontrado!")
        print("\n📋 Primeiros 1000 caracteres do HTML:")
        print(html[:1000])

except Exception as e:
    print(f"❌ Erro ao fazer requisição: {e}")
    import traceback
    traceback.print_exc()
