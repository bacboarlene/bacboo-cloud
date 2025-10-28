import requests
import time

# URL do seu servidor Flask no Render
API_RENDER = "https://bacbo-cloud.onrender.com/registrar"

# URL do site que fornece as jogadas (ajuste conforme seu endpoint real)
API_FONTE = "https://cassiniscore.com/api/backbull/latest"

print("🎯 Coletor Bacbo iniciado — intervalo de 3 s entre cada busca...\n")

while True:
    try:
        dados = requests.get(API_FONTE, timeout=10).json()

        print(f"🎲 Rodada: {dados.get('round_id')} | "
              f"Azul: {dados.get('dice_blue')} | "
              f"Vermelho: {dados.get('dice_red')} | "
              f"Vencedor: {dados.get('winner')}")

        resp = requests.post(API_RENDER, json=dados, timeout=10)
        if resp.status_code == 200:
            print("✅ Dados enviados com sucesso!\n")
        else:
            print(f"⚠️ Falha ao enviar ({resp.status_code})\n")

    except Exception as e:
        print("❌ Erro:", e)

    # Espera 3 segundos entre cada busca
    time.sleep(3)
