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
        return None, "texto_vazio"

    encontrados = re.findall(
        r"n[úu]mero do pedido[:\s]*([0-9]{6,})",
        texto,
        re.IGNORECASE
    )

    unicos = list(dict.fromkeys(encontrados))

    if len(unicos) == 1:
        return unicos[0], "ok"

    if len(unicos) > 1:
        return None, "multiplo"

    return None, "nao_encontrado"


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
        data = request.get_json(silent=True) or {}
        print("########## WEBHOOK NOVO RODANDO ##########", flush=True)
        print("=== WEBHOOK RECEBIDO ===", flush=True)
        print(data, flush=True)

        ticket = data.get("ticket", {})
        ticket_id = ticket.get("id")
        status = ticket.get("status")
        latest_comment = ticket.get("latest_comment", {}).get("body", "")

        print(f"ticket_id: {ticket_id}", flush=True)
        print(f"status: {status}", flush=True)
        print(f"latest_comment: {latest_comment}", flush=True)

        if not ticket_id:
            print("Ignorado: ticket_id ausente", flush=True)
            return jsonify({"status": "ignorado", "motivo": "ticket_id ausente"}), 200

        if status != "new":
            print("Ignorado: ticket não está como new", flush=True)
            return jsonify({"status": "ignorado", "motivo": "ticket não está como new"}), 200

        numero_pedido, motivo = extrair_numero_pedido(latest_comment)
        print(f"numero_pedido_extraido: {numero_pedido}", flush=True)
        print(f"motivo_extracao: {motivo}", flush=True)

        if motivo == "multiplo":
            return jsonify({
                "status": "ignorado",
                "motivo": "mais de um número do pedido encontrado"
            }), 200

        if not numero_pedido:
            return jsonify({
                "status": "ignorado",
                "motivo": "numero do pedido não encontrado"
            }), 200

        status_code, response_text = atualizar_campo_ticket(ticket_id, numero_pedido)
        print(f"Zendesk update status_code: {status_code}", flush=True)
        print(f"Zendesk update response: {response_text}", flush=True)

        if status_code not in (200, 201):
            return jsonify({
                "status": "erro_zendesk",
                "ticket_id": ticket_id,
                "numero_pedido": numero_pedido,
                "zendesk_status_code": status_code,
                "zendesk_response": response_text
            }), 500

        return jsonify({
            "status": "sucesso",
            "ticket_id": ticket_id,
            "numero_pedido": numero_pedido,
            "zendesk_status_code": status_code
        }), 200

    except Exception as e:
        print(f"ERRO NO WEBHOOK: {str(e)}", flush=True)
        return jsonify({"status": "erro", "mensagem": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
