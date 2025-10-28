from flask import Flask, request, jsonify
import csv, os, datetime

app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bacbo Cloud ativo no Render!"

@app.route("/teste")
def teste():
    return jsonify({"status": "online", "api": "bacbo"})

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

    return jsonify({"status": "ok", "arquivo": arquivo})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
