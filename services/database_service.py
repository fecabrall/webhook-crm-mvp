import os
from supabase import create_client, Client
from dotenv import load_dotenv

# Carrega variáveis de ambiente para não expor credenciais
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ ERRO CRÍTICO: Variáveis do Supabase não configuradas no .env")

# Inicializa conexão segura
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def insert_new_client(data: dict) -> tuple:
    """
    Insere cliente no Supabase.
    Segurança: Usa a biblioteca client do Supabase que previne SQL Injection.
    """
    try:
        # Tabela 'clientes' (Minúsculo é padrão Postgres/Supabase)
        response = supabase.table('clientes').insert(data).execute()
        
        # Verifica se houve resposta de dados (sucesso)
        if response.data:
            return response.data[0], None
        else:
            return None, "Erro desconhecido ao inserir."

    except Exception as e:
        return None, f"Erro de conexão com DB: {str(e)}"

def get_clients_for_automation() -> tuple:
    """
    Busca clientes para o Robô.
    """
    try:
        # Busca todos os campos. Em produção, liste apenas os campos necessários (SELECT nome, telefone...)
        response = supabase.table('clientes').select('*').execute()
        return response.data, None
    except Exception as e:
        return None, f"Erro ao buscar clientes: {str(e)}"


def update_client_status(client_id: int, novo_status: str) -> tuple:
    """
    Atualiza o status de um cliente no banco de dados.
    
    Args:
        client_id: ID do cliente
        novo_status: Novo status a ser atribuído
    
    Returns:
        Tuple[dict, Optional[str]]: (dados_atualizados, erro)
    """
    try:
        response = supabase.table('clientes').update({
            'status': novo_status
        }).eq('id', client_id).execute()
        
        if response.data:
            return response.data[0], None
        else:
            return None, "Cliente não encontrado ou nenhuma alteração realizada"
            
    except Exception as e:
        return None, f"Erro ao atualizar status: {str(e)}"


def get_all_clients() -> tuple:
    """
    Busca todos os clientes do banco de dados.
    Útil para o dashboard e relatórios.
    
    Returns:
        Tuple[list, Optional[str]]: (lista_de_clientes, erro)
    """
    try:
        response = supabase.table('clientes').select('*').order('created_at', desc=True).execute()
        return response.data, None
    except Exception as e:
        return None, f"Erro ao buscar clientes: {str(e)}"