from scrapling import DynamicFetcher, Selector
from datetime import date
import json
import re

# Configuração
game_base_path = "https://tips.gg/csgo/matches/"
target_date = date.today()
date_str = target_date.strftime("%d-%m-%Y")
test_url = f"{game_base_path}{date_str}/"

print(f"🔍 Testando Scrapling em: {test_url}\n")

try:
    # Criar fetcher dinâmico (carrega JavaScript)
    print("⏳ Carregando página com JavaScript...")
    fetcher = DynamicFetcher()
    response = fetcher.fetch(test_url)

    # Verificar atributos disponíveis
    print(f"📋 Atributos do response: {dir(response)}\n")

    # Tentar acessar o conteúdo
    html = response.text if hasattr(response, 'text') else str(response)

    print(f"📄 Tamanho do conteúdo: {len(html)} caracteres\n")

    # Procurar scripts JSON-LD
    print("🔎 Procurando scripts JSON-LD...\n")

    json_ld_scripts = re.findall(r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL)

    print(f"📊 Scripts JSON-LD encontrados: {len(json_ld_scripts)}\n")

    if json_ld_scripts:
        for i, script in enumerate(json_ld_scripts[:3], 1):
            try:
                data = json.loads(script)
                print(f"--- Script {i} ---")
                print(f"Tipo: {data.get('@type', 'N/A')}")

                if data.get('@type') == 'SportsEvent':
                    print(f"✅ É um SportsEvent!")
                    print(f"  - startDate: {data.get('startDate', 'N/A')}")
                    print(f"  - description: {data.get('description', 'N/A')[:60]}...")
                    competitors = data.get('competitor', [])
                    print(f"  - competitors: {len(competitors)}")
                    if len(competitors) >= 2:
                        print(f"    • {competitors[0].get('name', 'N/A')} vs {competitors[1].get('name', 'N/A')}")
                print()
            except json.JSONDecodeError as e:
                print(f"❌ Erro ao decodificar script {i}: {e}\n")
    else:
        print("⚠️ Nenhum script JSON-LD encontrado!")
        print("\n📋 Primeiros 500 caracteres do HTML:")
        print(html[:500])

except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
