import os
import logging
from flask import Blueprint, request, jsonify, current_app
from services.database_service import insert_new_client
from utils.validators import validate_phone, validate_email, sanitize_phone, sanitize_email
from datetime import datetime

# Configuração de logging
logger = logging.getLogger(__name__)

# Cria o Blueprint
webhooks_bp = Blueprint('webhooks', __name__)

# Token de segurança do .env
API_SECRET_TOKEN = os.getenv("API_SECRET_TOKEN")


@webhooks_bp.route('/webhook', methods=['POST'])
def receive_webhook():
    """
    Recebe dados de novos clientes.
    Segurança:
    1. Verifica Token de Autorização (Header).
    2. Valida se os dados obrigatórios existem.
    """

    # ============================================================
    # 1. AUTENTICAÇÃO DO WEBHOOK (CORRIGIDO)
    # ============================================================

    # Garantir que o token da aplicação existe
    if not API_SECRET_TOKEN:
        current_app.logger.error("❌ ERRO CRÍTICO: API_SECRET_TOKEN não definido no ambiente!")
        return jsonify({"error": "Server misconfigured (missing API_SECRET_TOKEN)"}), 500

    auth_header = request.headers.get("Authorization", "")
    alt_header = request.headers.get("X-API-Token", "")

    # Suporta "Bearer <TOKEN>" e token limpo
    provided_token = (
        auth_header.replace("Bearer ", "").strip()
        if auth_header else alt_header.strip()
    )

    if provided_token != API_SECRET_TOKEN:
        return jsonify({"error": "Acesso Negado. Token inválido."}), 403

    # ============================================================
    # 2. CAPTURA O JSON
    # ============================================================

    data = request.get_json()
    if not data:
        return jsonify({"error": "Payload JSON inválido ou vazio."}), 400

    # ============================================================
    # 3. VALIDAÇÃO DE CAMPOS OBRIGATÓRIOS
    # ============================================================

    required_fields = ['nome', 'telefone']
    for field in required_fields:
        if field not in data:
            logger.warning(f"Campo obrigatório ausente: {field}")
            return jsonify({"error": f"Campo obrigatório ausente: {field}"}), 400

    # ============================================================
    # 4. VALIDAÇÃO E SANITIZAÇÃO
    # ============================================================

    telefone = data.get('telefone', '').strip()
    email = data.get('email', '').strip() if data.get('email') else ''
    nome = data.get('nome', '').strip()
    status = str(data.get('status') or 'Novo Cliente - 1 compra').strip()
    observacoes = data.get('observacoes', '').strip() if data.get('observacoes') else ''
    dry_run = str(request.headers.get('X-Dry-Run', 'false')).lower() == 'true'

    # Telefone
    telefone_valido, erro_telefone = validate_phone(telefone)
    if not telefone_valido:
        return jsonify({"error": f"Telefone inválido: {erro_telefone}"}), 400

    # Email
    if email:
        email_valido, erro_email = validate_email(email)
        if not email_valido:
            return jsonify({"error": f"Email inválido: {erro_email}"}), 400

    # Nome
    if not nome or len(nome) < 2:
        return jsonify({"error": "Nome deve ter pelo menos 2 caracteres"}), 400

    telefone_sanitizado = sanitize_phone(telefone)
    email_sanitizado = sanitize_email(email) if email else ''

    # ============================================================
    # 5. PREPARAÇÃO DOS DADOS PARA O BANCO
    # ============================================================

    data_primeira_compra = data.get('data_primeira_compra')
    procedimento = data.get('procedimento', '')
    valor_pago = data.get('valor_pago')

    # Data primeira compra
    if data_primeira_compra:
        try:
            if isinstance(data_primeira_compra, str) and '/' in data_primeira_compra:
                from datetime import datetime as dt
                data_primeira_compra = dt.strptime(data_primeira_compra, '%d/%m/%Y').date().isoformat()
        except Exception as e:
            logger.warning(f"Data inválida recebida: {data_primeira_compra} - {e}")
            data_primeira_compra = None
    else:
        data_primeira_compra = datetime.now().date().isoformat()

    # Próxima ação automática (7 dias depois)
    proxima_acao = data.get('proxima_acao')
    if not proxima_acao and data_primeira_compra:
        try:
            from datetime import timedelta
            data_compra = datetime.fromisoformat(str(data_primeira_compra))
            proxima_acao = (data_compra + timedelta(days=7)).isoformat()
        except Exception as e:
            logger.warning(f"Erro ao calcular próxima ação: {e}")
            proxima_acao = None

    # Valor pago
    if valor_pago is not None:
        try:
            valor_pago = float(str(valor_pago).replace(',', '.'))
        except Exception:
            logger.warning(f"Valor pago inválido: {valor_pago}")
            valor_pago = None

    client_payload = {
        "nome": nome,
        "telefone": telefone_sanitizado,
        "email": email_sanitizado,
        "status": status or "Novo Cliente - 1 compra",
        "data_primeira_compra": data_primeira_compra,
        "procedimento": procedimento,
        "valor_pago": valor_pago,
        "proxima_acao": proxima_acao,
        "observacoes": observacoes
    }

    logger.info(f"Processando novo cliente: {nome} ({telefone_sanitizado})")

    # ============================================================
    # DRY RUN
    # ============================================================

    if dry_run:
        return jsonify({
            "dry_run": True,
            "normalized_payload": client_payload
        }), 200

    # ============================================================
    # 7. INSERÇÃO NO BANCO
    # ============================================================

    new_client, error = insert_new_client(client_payload)

    if error:
        logger.error(f"Erro ao salvar cliente: {error}")
        return jsonify({"error": f"Falha ao salvar no banco: {error}"}), 500

    logger.info(f"Cliente criado com sucesso: ID {new_client.get('id')}")

    return jsonify({
        "message": "Cliente recebido com sucesso!",
        "client_id": new_client.get('id'),
        "nome": new_client.get('nome')
    }), 201
