from flask import Flask, jsonify
import requests, csv, os, datetime, time, threading, pickle, base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================================
# 🌍 CONFIGURAÇÃO GERAL
# ==========================================================
URL_LATEST = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"
SCOPES = ['https://www.googleapis.com/auth/drive.file']
FOLDER_ID = '1-oK5YSVhb8ajwu-Pil-BiB4GiE841um1'
TOKEN_FILE = '/etc/secrets/token_drive_base64.txt'

app = Flask(__name__)

# ==========================================================
# ☁️ AUTENTICAÇÃO GOOGLE DRIVE
# ==========================================================
drive_service = None
try:
    with open(TOKEN_FILE, 'r', encoding='utf-8') as f:
        encoded = f.read().strip()
        data = base64.b64decode(encoded)
        with open('token_drive.pkl', 'wb') as t:
            t.write(data)
    with open('token_drive.pkl', 'rb') as token:
        creds = pickle.load(token)
    drive_service = build('drive', 'v3', credentials=creds)
    print("✅ Autenticado com sucesso no Google Drive.")
except Exception as e:
    print(f"⚠️ Falha ao autenticar Drive: {e}")

# ==========================================================
# ☁️ FUNÇÕES DE ENVIO AO DRIVE
# ==========================================================
def buscar_arquivo_drive(nome):
    try:
        query = f"'{FOLDER_ID}' in parents and name='{nome}' and trashed=false"
        results = drive_service.files().list(q=query, fields="files(id)").execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None
    except Exception as e:
        print(f"⚠️ Erro ao buscar arquivo no Drive: {e}")
        return None

def enviar_para_drive(arquivo_local):
    try:
        nome_arquivo = os.path.basename(arquivo_local)
        file_id = buscar_arquivo_drive(nome_arquivo)
        media = MediaFileUpload(arquivo_local, mimetype='text/csv')
        if file_id:
            drive_service.files().update(fileId=file_id, media_body=media).execute()
            print(f"☁️ Atualizado no Drive: {nome_arquivo}")
        else:
            metadata = {'name': nome_arquivo, 'parents': [FOLDER_ID]}
            drive_service.files().create(body=metadata, media_body=media).execute()
            print(f"☁️ Enviado novo arquivo para o Drive: {nome_arquivo}")
    except Exception as e:
        print(f"⚠️ Erro ao enviar para o Drive: {e}")

# ==========================================================
# 🕛 ENVIO AUTOMÁTICO À MEIA-NOITE
# ==========================================================
def rotina_meianoite():
    while True:
        agora = datetime.datetime.now()
        proxima = (agora + datetime.timedelta(days=1)).replace(hour=0, minute=0, second=5, microsecond=0)
        segundos = (proxima - agora).total_seconds()
        print(f"⏰ Próximo envio ao Drive: {proxima}")
        time.sleep(segundos)

        try:
            pasta = "dados"
            nome_arquivo = f"dados_{datetime.date.today()}.csv"
            arquivo = os.path.join(pasta, nome_arquivo)
            if os.path.exists(arquivo):
                enviar_para_drive(arquivo)
            novo_arquivo = os.path.join(pasta, f"dados_{datetime.date.today() + datetime.timedelta(days=1)}.csv")
            with open(novo_arquivo, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "datahora","id_rodada","azul_1","azul_2","vermelho_1","vermelho_2",
                    "soma_azul","soma_vermelho","vencedor","multiplier","payout","status"
                ])
            print(f"🌅 Novo CSV iniciado: {novo_arquivo}")
        except Exception as e:
            print(f"⚠️ Erro rotina meia-noite: {e}")

threading.Thread(target=rotina_meianoite, daemon=True).start()

# ==========================================================
# 🤖 COLETOR AUTOMÁTICO (executa direto no Render)
# ==========================================================
def coletar_dados():
    sess = requests.Session()
    ultimo_id = None
    os.makedirs("dados", exist_ok=True)
    os.makedirs("logs", exist_ok=True)
    print("🌐 Coletor Bacbo Cloud iniciado.")

    while True:
        try:
            r = sess.get(URL_LATEST, timeout=8)
            if r.status_code != 200:
                print(f"[ERRO HTTP] {r.status_code}")
                time.sleep(5)
                continue

            j = r.json()
            data = j.get("data", {})
            gid = data.get("id")
            if gid == ultimo_id or gid is None:
                time.sleep(2)
                continue

            res = data.get("result", {})
            player = res.get("playerDice", {})
            banker = res.get("bankerDice", {})

            a1, a2 = int(player.get("first", 0)), int(player.get("second", 0))
            v1, v2 = int(banker.get("first", 0)), int(banker.get("second", 0))
            soma_azul, soma_vermelho = a1 + a2, v1 + v2

            outcome = res.get("outcome", "Desconhecido")
            vencedor = {"PlayerWon": "Azul", "BankerWon": "Vermelho", "Tie": "Empate"}.get(outcome, outcome)
            multiplier = res.get("multiplier") or res.get("tieMultiplier") or ""
            payout = res.get("payout") or ""
            status = res.get("status") or data.get("status") or ""

            datahora = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            linha = [
                datahora, gid, a1, a2, v1, v2,
                soma_azul, soma_vermelho, vencedor,
                multiplier, payout, status
            ]

            nome_csv = f"dados/dados_{datetime.date.today()}.csv"
            novo_arquivo = not os.path.exists(nome_csv)
            with open(nome_csv, "a", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                if novo_arquivo:
                    writer.writerow([
                        "datahora","id_rodada","azul_1","azul_2","vermelho_1","vermelho_2",
                        "soma_azul","soma_vermelho","vencedor","multiplier","payout","status"
                    ])
                writer.writerow(linha)

            logfile = f"logs/log_{datetime.date.today()}.txt"
            with open(logfile, "a", encoding="utf-8") as log:
                log.write(f"[{datahora}] ID {gid} - {vencedor} ({soma_azul} x {soma_vermelho})\n")

            print(f"[OK] Rodada {gid}: {vencedor} ({soma_azul} x {soma_vermelho}) Mult:{multiplier}")
            ultimo_id = gid
            time.sleep(2)
        except Exception as e:
            print(f"[ERRO] {e}")
            time.sleep(5)

# Thread principal do coletor
threading.Thread(target=coletar_dados, daemon=True).start()

# ==========================================================
# 🌐 FLASK ROUTES
# ==========================================================
@app.route("/")
def home():
    return "✅ Bacbo Cloud Collector ativo — coleta automática + envio diário para o Drive."

@app.route("/ultima")
def ultima():
    """Retorna a última linha registrada localmente."""
    nome_arquivo = f"dados/dados_{datetime.date.today()}.csv"
    if not os.path.exists(nome_arquivo):
        return jsonify({"erro": "sem dados ainda"}), 404

    with open(nome_arquivo, "r", encoding="utf-8") as f:
        linhas = f.readlines()
        if len(linhas) <= 1:
            return jsonify({"erro": "nenhum registro"}), 404
        ultima = linhas[-1].strip().split(",")
        campos = [
            "datahora","id_rodada","azul_1","azul_2","vermelho_1","vermelho_2",
            "soma_azul","soma_vermelho","vencedor","multiplier","payout","status"
        ]
        return jsonify(dict(zip(campos, ultima)))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
