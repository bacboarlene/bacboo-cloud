# ==========================================================
# 🌐 Bacbo Cloud API — Render + Google Drive v4.1
# ==========================================================
from flask import Flask, request, jsonify, send_file
import csv, os, datetime, threading, time, pickle, base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# ==========================================================
# ☁️ CONFIGURAÇÃO GOOGLE DRIVE
# ==========================================================
SCOPES = ['https://www.googleapis.com/auth/drive.file']
TOKEN_PICKLE = 'token_drive.pkl'
FOLDER_ID = '1-oK5YSVhb8ajwu-Pil-BiB4GiE841um1'  # ID da pasta BacboCloud

# 🔹 Reconstrói token se existir variável de ambiente no Render
token_env = os.getenv("TOKEN_DRIVE_BASE64")
if token_env:
    try:
        with open(TOKEN_PICKLE, "wb") as f:
            f.write(base64.b64decode(token_env))
        print("🔐 Token reconstruído a partir da variável TOKEN_DRIVE_BASE64.")
    except Exception as e:
        print(f"⚠️ Falha ao reconstruir token: {e}")

# ==========================================================
# 🔹 Autenticação Drive
# ==========================================================
drive_service = None
try:
    if os.path.exists(TOKEN_PICKLE):
        with open(TOKEN_PICKLE, 'rb') as token:
            creds = pickle.load(token)
            if creds and creds.valid:
                drive_service = build('drive', 'v3', credentials=creds)
                print("✅ Autenticado com sucesso no Google Drive.")
            elif creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                drive_service = build('drive', 'v3', credentials=creds)
                print("🔄 Token Drive renovado.")
    else:
        print("⚠️ Token ausente ou inválido. Reenvie o token_drive.pkl.")
except Exception as e:
    print(f"⚠️ Falha ao autenticar Drive: {e}")

# ==========================================================
# 🧩 FUNÇÕES AUXILIARES CSV
# ==========================================================
def caminho_csv():
    os.makedirs("dados", exist_ok=True)
    return os.path.join("dados", f"dados_{datetime.date.today()}.csv")

def registrar_rodada(linha: dict):
    """Incrementa sem apagar CSV"""
    arquivo = caminho_csv()
    cabecalho = [
        "datahora", "id_rodada", "azul_1", "azul_2",
        "vermelho_1", "vermelho_2", "soma_azul", "soma_vermelho",
        "vencedor", "multiplier", "payout", "status"
    ]
    novo = not os.path.exists(arquivo)
    with open(arquivo, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=cabecalho)
        if novo:
            writer.writeheader()
        writer.writerow(linha)

def ler_csv(limite=None):
    arquivo = caminho_csv()
    if not os.path.exists(arquivo):
        return []
    with open(arquivo, "r", encoding="utf-8") as f:
        linhas = list(csv.DictReader(f))
    if limite:
        return linhas[-limite:]
    return linhas

def ultima_rodada():
    linhas = ler_csv()
    return linhas[-1] if linhas else {}

# ==========================================================
# ☁️ UPLOAD PARA O GOOGLE DRIVE
# ==========================================================
def enviar_para_drive():
    """Envia o CSV atual completo para o Google Drive"""
    if not drive_service:
        print("⚠️ Drive não autenticado, upload cancelado.")
        return
    try:
        arquivo = caminho_csv()
        if not os.path.exists(arquivo):
            print("⚠️ Nenhum CSV para enviar.")
            return
        nome = os.path.basename(arquivo)
        file_metadata = {'name': nome, 'parents': [FOLDER_ID]}
        media = MediaFileUpload(arquivo, mimetype='text/csv')
        drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"☁️ Enviado para o Drive: {nome}")
    except Exception as e:
        print(f"⚠️ Erro ao enviar para o Drive: {e}")

# ==========================================================
# ⏰ ROTINA AUTOMÁTICA MEIA-NOITE
# ==========================================================
def rotina_drive_diaria():
    while True:
        agora = datetime.datetime.now()
        if agora.hour == 0 and agora.minute == 0:
            enviar_para_drive()
            print("🕛 Upload automático concluído.")
            time.sleep(60)
        time.sleep(5)

threading.Thread(target=rotina_drive_diaria, daemon=True).start()

# ==========================================================
# 🌍 FLASK API
# ==========================================================
app = Flask(__name__)

@app.route("/")
def home():
    return "🏠 Bacbo Cloud ativo — v4.1"

@app.route("/ping")
def ping():
    return jsonify({"status": "online", "hora": datetime.datetime.now().isoformat()})

@app.route("/registrar", methods=["POST"])
def registrar():
    data = request.json
    if not data:
        return jsonify({"erro": "sem dados"}), 400

    soma_azul = data.get("azul_1", 0) + data.get("azul_2", 0)
    soma_vermelho = data.get("vermelho_1", 0) + data.get("vermelho_2", 0)
    linha = {
        "datahora": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "id_rodada": data.get("id_rodada"),
        "azul_1": data.get("azul_1"),
        "azul_2": data.get("azul_2"),
        "vermelho_1": data.get("vermelho_1"),
        "vermelho_2": data.get("vermelho_2"),
        "soma_azul": soma_azul,
        "soma_vermelho": soma_vermelho,
        "vencedor": data.get("vencedor"),
        "multiplier": data.get("multiplier"),
        "payout": data.get("payout"),
        "status": data.get("status", "Resolved")
    }
    registrar_rodada(linha)
    return jsonify({"status": "ok", "rodada": linha})

@app.route("/ultima")
def rota_ultima():
    return jsonify(ultima_rodada())

@app.route("/historico")
def rota_historico():
    limite = request.args.get("limite", default=100, type=int)
    return jsonify(ler_csv(limite))

@app.route("/baixar")
def baixar():
    arquivo = caminho_csv()
    if not os.path.exists(arquivo):
        return jsonify({"erro": "nenhum CSV encontrado"}), 404
    return send_file(arquivo, as_attachment=True)

@app.route("/forcar_upload")
def forcar_upload():
    enviar_para_drive()
    return jsonify({"status": "ok", "mensagem": "Upload manual concluído."})

# ==========================================================
# 🚀 INICIALIZAÇÃO
# ==========================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
