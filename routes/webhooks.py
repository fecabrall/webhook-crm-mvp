import os
from flask import Blueprint, request, jsonify
from services.database_service import insert_new_client
from datetime import datetime

# Cria o "Blueprint" (um pedaço modular da aplicação)
webhooks_bp = Blueprint('webhooks', __name__)

# Token de segurança definido no .env
API_SECRET_TOKEN = os.getenv("API_SECRET_TOKEN")

@webhooks_bp.route('/webhook', methods=['POST'])
def receive_webhook():
    """
    Recebe dados de novos clientes.
    Segurança:
    1. Verifica Token de Autorização (Header).
    2. Valida se os dados obrigatórios existem.
    """
    
    # 1. Autenticação do Webhook (Segurança de API)
    auth_header = request.headers.get('Authorization')
    # Espera receber: "Bearer seu_token_aqui" ou apenas o token
    if not auth_header or API_SECRET_TOKEN not in auth_header:
        return jsonify({"error": "Acesso Negado. Token inválido."}), 403

    # 2. Captura o JSON enviado
    data = request.get_json()
    if not data:
        return jsonify({"error": "Payload JSON inválido ou vazio."}), 400

    # 3. Validação de Campos Obrigatórios (Data Validation)
    required_fields = ['nome', 'telefone']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Campo obrigatório ausente: {field}"}), 400

    # 4. Preparação dos dados para o Banco (Sanitização básica)
    # Definimos um status inicial padrão se não vier na requisição
    client_payload = {
        "nome": data.get('nome'),
        "telefone": data.get('telefone'), # Ideal: validar formato (regex) aqui futuramente
        "email": data.get('email', ''),   # Opcional
        "status": "Novo Cliente - 1 compra",
        "created_at": datetime.now().isoformat()
    }

    # 5. Inserção Segura no Banco
    new_client, error = insert_new_client(client_payload)

    if error:
        return jsonify({"error": f"Falha ao salvar no banco: {error}"}), 500

    return jsonify({
        "message": "Cliente recebido com sucesso!",
        "client_id": new_client.get('id')
    }), 201