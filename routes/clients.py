from flask import Blueprint, jsonify, request
from services.database_service import supabase

clients_bp = Blueprint('clients', __name__)

@clients_bp.route('/clients', methods=['GET'])
def list_clients():
    """
    Retorna a lista de clientes do banco de dados.
    Pode ser usado para integrações futuras ou debug.
    """
    try:
        # Paginação simples (opcional, aqui pegamos tudo)
        response = supabase.table('clientes').select('*').execute()
        return jsonify(response.data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@clients_bp.route('/clients/<int:client_id>', methods=['GET'])
def get_client(client_id):
    """
    Retorna um cliente específico pelo ID.
    """
    try:
        response = supabase.table('clientes').select('*').eq('id', client_id).execute()
        if response.data:
            return jsonify(response.data[0]), 200
        return jsonify({"error": "Cliente não encontrado"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500