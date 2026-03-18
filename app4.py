import os
import re
import requests
from flask import Flask, request, jsonify

app = Flask(__name__)

ZENDESK_SUBDOMAIN = os.environ.get("ZENDESK_SUBDOMAIN")
ZENDESK_EMAIL = os.environ.get("ZENDESK_EMAIL")
ZENDESK_API_TOKEN = os.environ.get("ZENDESK_API_TOKEN")
CAMPO_NUMERO_PEDIDO = os.environ.get("CAMPO_NUMERO_PEDIDO")


def extrair_numero_pedido(texto):
    if not texto:
        return None

    padroes = [
        r"numero do pedido[:\s]*([0-9]{6,})",
        r"número do pedido[:\s]*([0-9]{6,})",
        r"pedido interno[:\s]*([0-9]{6,})",
        r"\b([0-9]{6,})\b"
    ]

    texto_limpo = texto.lower()

    for padrao in padroes:
        match = re.search(padrao, texto_limpo, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def atualizar_campo_ticket(ticket_id, numero_pedido):
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets/{ticket_id}.json"

    payload = {
        "ticket": {
            "custom_fields": [
                {
                    "id": int(CAMPO_NUMERO_PEDIDO),
                    "value": numero_pedido
                }
            ]
        }
    }

    response = requests.put(
        url,
        json=payload,
        auth=(f"{ZENDESK_EMAIL}/token", ZENDESK_API_TOKEN),
        headers={"Content-Type": "application/json"}
    )

    return response.status_code, response.text


@app.route("/", methods=["GET"])
def home():
    return "App rodando com sucesso.", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        data = request.json or {}

        ticket = data.get("ticket", {})
        ticket_id = ticket.get("id")
        status = ticket.get("status")
        latest_comment = ticket.get("latest_comment", {}).get("body", "")

        if not ticket_id:
            return jsonify({"status": "ignorado", "motivo": "ticket_id ausente"}), 200

        if status != "new":
            return jsonify({"status": "ignorado", "motivo": "ticket não está como new"}), 200

        numero_pedido = extrair_numero_pedido(latest_comment)

        if not numero_pedido:
            return jsonify({"status": "ignorado", "motivo": "numero do pedido não encontrado"}), 200

        status_code, response_text = atualizar_campo_ticket(ticket_id, numero_pedido)

        return jsonify({
            "status": "sucesso",
            "ticket_id": ticket_id,
            "numero_pedido": numero_pedido,
            "zendesk_status_code": status_code,
            "zendesk_response": response_text
        }), 200

    except Exception as e:
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)