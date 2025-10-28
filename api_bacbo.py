# ==========================================================
# 🌐 BacBo Cloud Collector v4.2 – Render Stable
# ==========================================================
from flask import Flask, jsonify, send_file, request
import os, csv, datetime, time, threading, base64, pickle, io, requests, traceback
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# ==========================================================
# ☁️ GOOGLE DRIVE CONFIG
# ==========================================================
FOLDER_ID = "1-oK5YSVhb8ajwu-Pil-BiB4GiE841um1"
SCOPES = ['https://www.googleapis.com/auth/drive.file']
TOKEN_BASE64 = os.environ.get("TOKEN_DRIVE_BASE64")

drive_service = None

def autenticar_drive():
    """Autentica via token codificado TOKEN_DRIVE_BASE64"""
    global drive_service
    try:
        if not TOKEN_BASE64:
            print("⚠️ TOKEN_DRIVE_BASE64 ausente.")
            return None

        creds = pickle.loads(base64.b64decode(TOKEN_BASE64))
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())

        drive_service = build('drive', 'v3', credentials=creds)
        print("✅ Autenticado com sucesso no Google Drive.")
        return drive_service
    except Exception as e:
        print(f"⚠️ Falha ao autenticar Drive: {e}")
        return None

autenticar_drive()

def enviar_para_drive(arquivo_local):
    """Envia o CSV atual para o Google Drive"""
    if not drive_service:
        print("⚠️ Drive não autenticado, upload cancelado.")
        return
    try:
        nome_arquivo = os.path.basename(arquivo_local)
        file_metadata = {'name': nome_arquivo, 'parents': [FOLDER_ID]}
        media = MediaFileUpload(arquivo_local, mimetype='text/csv')
        try:
            drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        except Exception:
            # se pasta não tiver permissão, envia para raiz
            file_metadata.pop('parents', None)
            drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"☁️ CSV enviado ao Drive: {nome_arquivo}")
    except Exception as e:
        print(f"⚠️ Erro ao enviar para o Drive: {e}")

# ==========================================================
# 🎲 COLETOR DE DADOS
# ==========================================================
URL_LATEST = "https://api.casinoscores.com/svc-evolution-game-events/api/bacbo/latest"
ultimo_id = None
coleta_ativa = False

os.makedirs("dados", exist_ok=True)
os.makedirs("logs", exist_ok=True)

def registrar_erro(msg):
    with open("logs/erros.txt", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now()}] {msg}\n")

def coletar_dados():
    """Coleta em loop contínuo"""
    global ultimo_id, coleta_ativa
    if coleta_ativa:
        print("🌀 Coleta já em execução, ignorando inicialização duplicada.")
        return
    coleta_ativa = True
    sess = requests.Session()
    print("🌐 Coleta iniciada (modo contínuo a cada 3 s).")

    while True:
        try:
            r = sess.get(URL_LATEST, timeout=8)
            if r.status_code != 200:
                time.sleep(4)
                continue

            j = r.json()
            data = j.get("data", {})
            gid = data.get("id")
            if not gid or gid == ultimo_id:
                time.sleep(3)
                continue

            res = data.get("result", {})
            a1 = int(res.get("playerDice", {}).get("first", 0))
            a2 = int(res.get("playerDice", {}).get("second", 0))
            v1 = int(res.get("bankerDice", {}).get("first", 0))
            v2 = int(res.get("bankerDice", {}).get("second", 0))
            soma_azul, soma_verm = a1 + a2, v1 + v2

            outcome = res.get("outcome", "")
            vencedor = {"PlayerWon": "Azul", "BankerWon": "Vermelho", "Tie": "Empate"}.get(outcome, "Desconhecido")

            linha = {
                "datahora": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "id_rodada": gid,
                "azul_1": a1, "azul_2": a2,
                "vermelho_1": v1, "vermelho_2": v2,
                "soma_azul": soma_azul, "soma_vermelho": soma_verm,
                "vencedor": vencedor,
                "multiplier": res.get("multiplier") or res.get("tieMultiplier") or "",
                "payout": res.get("payout") or "",
                "status": res.get("status") or data.get("status") or ""
            }

            nome_csv = f"dados/dados_{datetime.date.today()}.csv"
            cabecalho = list(linha.keys())
            novo_arquivo = not os.path.exists(nome_csv)
            with open(nome_csv, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cabecalho)
                if novo_arquivo: w.writeheader()
                w.writerow(linha)

            nome_hist = "dados/historico_bacbo.csv"
            novo_hist = not os.path.exists(nome_hist)
            with open(nome_hist, "a", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=cabecalho)
                if novo_hist: w.writeheader()
                w.writerow(linha)

            print(f"[OK] {gid}: {vencedor} ({soma_azul}x{soma_verm})")
            ultimo_id = gid
            time.sleep(3)

        except Exception as e:
            registrar_erro(traceback.format_exc())
            print(f"[ERRO] {e}")
            time.sleep(5)

# ==========================================================
# ⏰ UPLOAD AUTOMÁTICO À MEIA-NOITE
# ==========================================================
def agendar_upload():
    while True:
        try:
            agora = datetime.datetime.now(datetime.timezone.utc).astimezone(datetime.timezone(datetime.timedelta(hours=-3)))
            if agora.hour == 0 and agora.minute == 0:
                nome_csv = f"dados/dados_{agora.date()}.csv"
                if os.path.exists(nome_csv):
                    enviar_para_drive(nome_csv)
                time.sleep(60)
            time.sleep(20)
        except Exception as e:
            registrar_erro(f"Erro upload agendado: {e}")
            time.sleep(30)

# ==========================================================
# 🌐 FLASK ENDPOINTS
# ==========================================================
app = Flask(__name__)

@app.route("/")
def home():
    return "🌐 BacBo Cloud Collector v4.2 ativo."

@app.route("/ping")
def ping():
    return jsonify({"status": "online"})

@app.route("/ultima")
def ultima():
    nome_hist = "dados/historico_bacbo.csv"
    if not os.path.exists(nome_hist):
        return jsonify({"erro": "Sem histórico ainda"})
    with open(nome_hist, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
        return jsonify(linhas[-1] if linhas else {})

@app.route("/historico")
def historico():
    limite = int(request.args.get("limite", 100))
    nome_hist = "dados/historico_bacbo.csv"
    if not os.path.exists(nome_hist):
        return jsonify([])
    with open(nome_hist, encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    return jsonify(linhas[-limite:])

@app.route("/baixar")
def baixar():
    nome_csv = f"dados/dados_{datetime.date.today()}.csv"
    if os.path.exists(nome_csv):
        return send_file(nome_csv, as_attachment=True)
    return jsonify({"erro": "Nenhum CSV encontrado."})

@app.route("/forcar_upload")
def forcar_upload():
    nome_csv = f"dados/dados_{datetime.date.today()}.csv"
    if os.path.exists(nome_csv):
        enviar_para_drive(nome_csv)
        return jsonify({"status": "Upload forçado concluído."})
    return jsonify({"erro": "Nenhum CSV para enviar."})

@app.route("/status")
def status():
    nome_hist = "dados/historico_bacbo.csv"
    total = 0
    ultima = {}
    if os.path.exists(nome_hist):
        with open(nome_hist, encoding="utf-8") as f:
            linhas = list(csv.DictReader(f))
            total = len(linhas)
            if linhas:
                ultima = linhas[-1]
    return jsonify({
        "status": "online",
        "total_registros": total,
        "ultima_rodada": ultima.get("id_rodada", ""),
        "vencedor": ultima.get("vencedor", ""),
        "hora_atual": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })

# ==========================================================
# 🚀 INICIALIZAÇÃO COM ATRASO CONTROLADO
# ==========================================================
def iniciar_threads():
    print("⏳ Aguardando inicialização completa do servidor...")
    time.sleep(5)
    threading.Thread(target=coletar_dados, daemon=True).start()
    threading.Thread(target=agendar_upload, daemon=True).start()
    print("✅ Threads de coleta e upload iniciadas.")

if __name__ == "__main__":
    threading.Thread(target=iniciar_threads, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
