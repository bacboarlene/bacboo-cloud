from flask import Flask, request, jsonify
import csv, os, datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================================
# ☁️ CONFIGURAÇÃO GOOGLE DRIVE
# ==========================================================
SCOPES = ['https://www.googleapis.com/auth/drive']
SERVICE_ACCOUNT_FILE = 'credentials.json'  # nome do arquivo baixado do Google Cloud
FOLDER_ID = '1-oK5YSVhb8ajwu-Pil-BiB4GiE841um1'  # ID da pasta BacboCloud no Drive

creds = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES)
drive_service = build('drive', 'v3', credentials=creds)

def enviar_para_drive(arquivo_local):
    """Faz upload automático do CSV para o Google Drive"""
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
    return "✅ Bacbo Cloud ativo no Render + Google Drive!"

@app.route("/registrar", methods=["POST"])
def registrar():
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

    # ⬆️ Envia o CSV atualizado pro Google Drive
    enviar_para_drive(arquivo)

    return jsonify({"status": "ok", "arquivo": arquivo})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
