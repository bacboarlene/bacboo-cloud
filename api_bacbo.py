from flask import Flask, request, jsonify
import csv, os, datetime, pickle, base64, io
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# ==========================================================
# ☁️ CONFIGURAÇÃO GOOGLE DRIVE (OAuth Pessoal)
# ==========================================================
SCOPES = ['https://www.googleapis.com/auth/drive.file']
CLIENT_SECRET_FILE = 'client_secret.json'  # arquivo JSON do Google Cloud
TOKEN_BASE64_FILE = 'token_drive_base64.txt'  # token em Base64 para o Render
FOLDER_ID = '1-oK5YSVhb8ajwu-Pil-BiB4GiE841um1'  # ID da pasta no Drive


def autenticar_drive():
    """Autentica no Google Drive usando token Base64 (seguro para Render)."""
    creds = None
    try:
        if os.path.exists(TOKEN_BASE64_FILE):
            with open(TOKEN_BASE64_FILE, "r", encoding="utf-8") as f:
                data = base64.b64decode(f.read())
                creds = pickle.load(io.BytesIO(data))

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                print("♻️ Token atualizado automaticamente.")
            else:
                print("⚠️ Token ausente ou inválido. Gere novamente localmente.")
                return None

        print("✅ Autenticado com sucesso no Google Drive.")
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"⚠️ Falha ao autenticar Drive: {e}")
        return None


drive_service = autenticar_drive()


def enviar_para_drive(arquivo_local):
    """Envia o CSV atualizado para a pasta BacboCloud no Google Drive."""
    if not drive_service:
        print("⚠️ Drive não autenticado — arquivo não enviado.")
        return

    try:
        nome_arquivo = os.path.basename(arquivo_local)
        file_metadata = {'name': nome_arquivo, 'parents': [FOLDER_ID]}
        media = MediaFileUpload(arquivo_local, mimetype='text/csv')
        drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        print(f"☁️ Enviado para o Drive: {nome_arquivo}")
    except Exception as e:
        print(f"⚠️ Erro ao enviar para o Drive: {e}")


# ==========================================================
# 🌐 SERVIDOR FLASK
# ==========================================================
app = Flask(__name__)


@app.route("/")
def home():
    return "✅ Bacbo Cloud ativo no Render + Google Drive Base64!"


@app.route("/registrar", methods=["POST"])
def registrar():
    """Registra uma nova rodada e envia o CSV para o Drive."""
    data = request.json
    if not data:
        return jsonify({"erro": "sem dados"}), 400

    pasta = "dados"
    os.makedirs(pasta, exist_ok=True)
    arquivo = os.path.join(pasta, f"{datetime.date.today()}.csv")
    novo = not os.path.exists(arquivo)

    with open(arquivo, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if novo:
            writer.writerow(["id", "azul", "vermelho", "vencedor", "data"])
        writer.writerow([
            data.get("round_id"),
            data.get("dice_blue"),
            data.get("dice_red"),
            data.get("winner"),
            datetime.datetime.now().isoformat()
        ])

    enviar_para_drive(arquivo)
    return jsonify({"status": "ok", "arquivo": arquivo})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
