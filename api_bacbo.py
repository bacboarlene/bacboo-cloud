# ==========================================================
# 🎲 BacBo Cloud – Coleta Simples de Rodadas (v1.0)
# ==========================================================
from flask import Flask, jsonify
import os, csv, time, datetime, threading, requests

# URL da API oficial do BacBo (Evolution)
URL_LATEST = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"

# Pastas locais
os.makedirs("dados", exist_ok=True)
os.makedirs("logs", exist_ok=True)

# Controle interno
ultimo_id = None
coletando = False

# ==========================================================
# 🧠 Função principal de coleta
# ==========================================================
def coletar_dados():
    """Loop que coleta rodadas e salva no CSV a cada 3 segundos"""
    global ultimo_id, coletando
    if coletando:
        print("🌀 Coleta já está rodando...")
        return
    coletando = True

    print("🌐 Iniciando coleta de rodadas BacBo...")
    sess = requests.Session()

    while True:
        try:
            r = sess.get(URL_LATEST, timeout=6)
            if r.status_code != 200:
                time.sleep(3)
                continue

            j = r.json()
            data = j.get("data", {})
            gid = data.get("id")
            if not gid or gid == ultimo_id:
                time.sleep(2)
                continue

            res = data.get("result", {})
            player = res.get("playerDice", {})
            banker = res.get("bankerDice", {})

            a1, a2 = int(player.get("first", 0)), int(player.get("second", 0))
            v1, v2 = int(banker.get("first", 0)), int(banker.get("second", 0))

            soma_azul = a1 + a2
            soma_vermelho = v1 + v2

            outcome = res.get("outcome", "")
            vencedor = {
                "PlayerWon": "Azul",
                "BankerWon": "Vermelho",
                "Tie": "Empate"
            }.get(outcome, "Desconhecido")

            multiplier = res.get("multiplier") or res.get("tieMultiplier") or ""
            payout = res.get("payout") or ""
            status = res.get("status") or data.get("status") or ""

            datahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            linha = {
                "datahora": datahora,
                "id_rodada": gid,
                "azul_1": a1,
                "azul_2": a2,
                "vermelho_1": v1,
                "vermelho_2": v2,
                "soma_azul": soma_azul,
                "soma_vermelho": soma_vermelho,
                "vencedor": vencedor,
                "multiplier": multiplier,
                "payout": payout,
                "status": status
            }

            nome_csv = f"dados/dados_{datetime.date.today()}.csv"
            cabecalho = list(linha.keys())
            novo_arquivo = not os.path.exists(nome_csv)

            with open(nome_csv, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cabecalho)
                if novo_arquivo:
                    w.writeheader()
                w.writerow(linha)

            print(f"[OK] {gid}: {vencedor} ({soma_azul}x{soma_vermelho})")

            ultimo_id = gid
            time.sleep(3)

        except Exception as e:
            print(f"[ERRO] {e}")
            time.sleep(5)

# ==========================================================
# 🌐 Flask app — apenas status e última rodada
# ==========================================================
app = Flask(__name__)

@app.route("/")
def home():
    return "🎲 BacBo Cloud – Coleta Simples de CSV"

@app.route("/ultima")
def ultima():
    nome_csv = f"dados/dados_{datetime.date.today()}.csv"
    if not os.path.exists(nome_csv):
        return jsonify({"erro": "Sem rodadas coletadas ainda"})
    with open(nome_csv, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
        return jsonify(linhas[-1] if linhas else {})

@app.route("/historico")
def historico():
    nome_csv = f"dados/dados_{datetime.date.today()}.csv"
    if not os.path.exists(nome_csv):
        return jsonify([])
    with open(nome_csv, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
        return jsonify(linhas[-50:])

# ==========================================================
# 🚀 Inicialização
# ==========================================================
def iniciar():
    threading.Thread(target=coletar_dados, daemon=True).start()

if __name__ == "__main__":
    iniciar()
    app.run(host="0.0.0.0", port=10000)
