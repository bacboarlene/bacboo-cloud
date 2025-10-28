from flask import Flask, request, jsonify
import csv, os, datetime, pickle, base64
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ==========================================================
# ☁️ CONFIGURAÇÃO GOOGLE DRIVE
# ==========================================================
SCOPES = ['https://www.googleapis.com/auth/drive.file']
FOLDER_ID = '1-oK5YSVhb8ajwu-Pil-BiB4GiE841um1'
TOKEN_FILE = '/etc/secrets/token_drive_base64.txt'

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
# ☁️ UPLOAD / SINCRONIZAÇÃO COM O DRIVE
# ==========================================================
def buscar_arquivo_drive(nome):
    """Procura um arquivo pelo nome na pasta BacboCloud"""
    try:
        query = f"'{FOLDER_ID}' in parents and name='{nome}' and trashed=false"
        results = drive_service.files().list(q=query, fields="files(id, name)").execute()
        files = results.get('files', [])
        return files[0]['id'] if files else None
    except Exception as e:
        print(f"⚠️ Erro ao buscar arquivo no Drive: {e}")
        return None

def enviar_para_drive_sobrescrever(file_id, arquivo_local):
    """Atualiza ou cria o arquivo CSV no Drive"""
    try:
        nome_arquivo = os.path.basename(arquivo_local)
        media = MediaFileUpload(arquivo_local, mimetype='text/csv')
        if file_id:
            drive_service.files().update(fileId=file_id, media_body=media).execute()
            print(f"☁️ Atualizado no Drive: {nome_arquivo}")
        else:
            file_metadata = {'name': nome_arquivo, 'parents': [FOLDER_ID]}
            drive_service.files().create(body=file_metadata, media_body=media, fields='id').execute()
            print(f"☁️ Criado novo CSV no Drive: {nome_arquivo}")
    except Exception as e:
        print(f"⚠️ Erro ao enviar para o Drive: {e}")

# ==========================================================
# 🌐 SERVIDOR FLASK
# ==========================================================
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bacbo Cloud ativo – histórico local + Drive sincronizado."

@app.route("/registrar", methods=["POST"])
def registrar():
    data = request.json
    if not data:
        return jsonify({"erro": "sem dados"}), 400

    pasta = "dados"
    os.makedirs(pasta, exist_ok=True)
    nome_arquivo = f"{datetime.date.today()}.csv"
    arquivo = os.path.join(pasta, nome_arquivo)
    novo = not os.path.exists(arquivo)

    # Grava localmente
    with open(arquivo, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if novo:
            writer.writerow([
                "datahora","id_rodada","azul_1","azul_2","vermelho_1","vermelho_2",
                "soma_azul","soma_vermelho","vencedor","multiplier","payout","status"
            ])
        azul = data.get("dice_blue", [0,0])
        vermelho = data.get("dice_red", [0,0])
        soma_azul = sum(azul)
        soma_vermelho = sum(vermelho)
        writer.writerow([
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            data.get("round_id",""),
            azul[0], azul[1],
            vermelho[0], vermelho[1],
            soma_azul, soma_vermelho,
            data.get("winner",""),
            data.get("multiplier",""),
            data.get("payout",""),
            data.get("status","Resolved")
        ])

    # Atualiza Drive com arquivo completo
    file_id = buscar_arquivo_drive(nome_arquivo)
    enviar_para_drive_sobrescrever(file_id, arquivo)

    return jsonify({"status": "ok", "arquivo": nome_arquivo})

@app.route("/ultima", methods=["GET"])
def ultima():
    """Retorna a última linha registrada localmente."""
    pasta = "dados"
    nome_arquivo = f"{datetime.date.today()}.csv"
    arquivo = os.path.join(pasta, nome_arquivo)
    if not os.path.exists(arquivo):
        return jsonify({"erro": "sem arquivo local"}), 404

    with open(arquivo, "r", encoding="utf-8") as f:
        linhas = f.readlines()
        if len(linhas) <= 1:
            return jsonify({"erro": "nenhum registro ainda"}), 404
        ultima = linhas[-1].strip().split(",")
        campos = [
            "datahora","id_rodada","azul_1","azul_2","vermelho_1","vermelho_2",
            "soma_azul","soma_vermelho","vencedor","multiplier","payout","status"
        ]
        return jsonify(dict(zip(campos, ultima)))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
