import logging
from flask import Blueprint, jsonify, request
from services.database_service import get_all_clients

# Configuração de logging
logger = logging.getLogger(__name__)

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/clients', methods=['GET'])
def list_clients():
    """
    Retorna a lista de clientes do banco de dados.
    Pode ser usado para integrações futuras ou debug.
    """
    try:
        clients, error = get_all_clients()
        if error:
            logger.error(f"Erro ao buscar clientes: {error}")
            return jsonify({"error": error}), 500
        return jsonify(clients), 200
    except Exception as e:
        logger.error(f"Erro inesperado ao listar clientes: {str(e)}")
        return jsonify({"error": str(e)}), 500

@clients_bp.route('/clients/<int:client_id>', methods=['GET'])
def get_client(client_id):
    """
    Retorna um cliente específico pelo ID.
    """
    try:
        from services.database_service import supabase
        response = supabase.table('clientes').select('*').eq('id', client_id).execute()
        if response.data:
            return jsonify(response.data[0]), 200
        logger.warning(f"Cliente não encontrado: ID {client_id}")
        return jsonify({"error": "Cliente não encontrado"}), 404
    except Exception as e:
        logger.error(f"Erro ao buscar cliente {client_id}: {str(e)}")
        return jsonify({"error": str(e)}), 500