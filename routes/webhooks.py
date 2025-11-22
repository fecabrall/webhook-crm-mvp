import os
import logging
from flask import Blueprint, request, jsonify
from services.database_service import insert_new_client
from utils.validators import validate_phone, validate_email, sanitize_phone, sanitize_email
from datetime import datetime

# Configuração de logging
logger = logging.getLogger(__name__)

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
            logger.warning(f"Tentativa de webhook sem campo obrigatório: {field}")
            return jsonify({"error": f"Campo obrigatório ausente: {field}"}), 400

    # 4. Validação e Sanitização de Dados
    telefone = data.get('telefone', '').strip()
    email = data.get('email', '').strip() if data.get('email') else ''
    nome = data.get('nome', '').strip()
    
    # Valida telefone
    telefone_valido, erro_telefone = validate_phone(telefone)
    if not telefone_valido:
        logger.warning(f"Telefone inválido recebido: {telefone} - {erro_telefone}")
        return jsonify({"error": f"Telefone inválido: {erro_telefone}"}), 400
    
    # Valida email (se fornecido)
    if email:
        email_valido, erro_email = validate_email(email)
        if not email_valido:
            logger.warning(f"Email inválido recebido: {email} - {erro_email}")
            return jsonify({"error": f"Email inválido: {erro_email}"}), 400
    
    # Valida nome
    if not nome or len(nome) < 2:
        logger.warning(f"Nome inválido recebido: {nome}")
        return jsonify({"error": "Nome deve ter pelo menos 2 caracteres"}), 400
    
    # 5. Sanitização dos dados
    telefone_sanitizado = sanitize_phone(telefone)
    email_sanitizado = sanitize_email(email) if email else ''
    
    # 6. Preparação dos dados para o Banco
    client_payload = {
        "nome": nome,
        "telefone": telefone_sanitizado,
        "email": email_sanitizado,
        "status": "Novo Cliente - 1 compra",
        "created_at": datetime.now().isoformat()
    }
    
    logger.info(f"Processando novo cliente: {nome} ({telefone_sanitizado})")

    # 7. Inserção Segura no Banco
    new_client, error = insert_new_client(client_payload)

    if error:
        logger.error(f"Erro ao salvar cliente no banco: {error}")
        return jsonify({"error": f"Falha ao salvar no banco: {error}"}), 500

    logger.info(f"✅ Cliente criado com sucesso: ID {new_client.get('id')}")
    
    return jsonify({
        "message": "Cliente recebido com sucesso!",
        "client_id": new_client.get('id'),
        "nome": new_client.get('nome')
    }), 201