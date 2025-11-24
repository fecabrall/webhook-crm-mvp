import os
from supabase import create_client, Client
from dotenv import load_dotenv
from datetime import datetime

# Carrega variáveis de ambiente para não expor credenciais
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ ERRO CRÍTICO: Variáveis do Supabase não configuradas no .env")

# Inicializa conexão segura
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def insert_new_client(data: dict) -> tuple:
    try:
        allowed = {
            'nome','telefone','email','status','data_primeira_compra',
            'procedimento','valor_pago','proxima_acao','observacoes','ultima_acao'
        }
        payload = {k: v for k, v in data.items() if k in allowed}
        response = supabase.table('clientes').insert(payload).execute()
        if response.data:
            return response.data[0], None
        error_msg = getattr(response, 'error', None)
        return None, str(error_msg) if error_msg else "Erro desconhecido ao inserir."
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


# ============================================
# FUNÇÕES PARA TABELA AÇÕES
# ============================================

def insert_action(acao_data: dict) -> tuple:
    """
    Insere uma nova ação na tabela ações.
    
    Args:
        acao_data: Dicionário com dados da ação
            - id_cliente: ID do cliente
            - tipo: 'mensagem' ou 'ligacao'
            - conteudo: Conteúdo da mensagem ou notas
            - resultado: 'sim', 'nao', 'sem_resposta', 'agendou', 'comprou', 'pendente'
    
    Returns:
        Tuple[dict, Optional[str]]: (acao_criada, erro)
    """
    try:
        response = supabase.table('acoes').insert(acao_data).execute()
        if response.data:
            return response.data[0], None
        else:
            return None, "Erro desconhecido ao inserir ação"
    except Exception as e:
        return None, f"Erro ao inserir ação: {str(e)}"


def get_actions_by_client(client_id: int) -> tuple:
    """
    Busca todas as ações de um cliente específico.
    
    Args:
        client_id: ID do cliente
    
    Returns:
        Tuple[list, Optional[str]]: (lista_de_acoes, erro)
    """
    try:
        response = supabase.table('acoes').select('*').eq('id_cliente', client_id).order('data', desc=True).execute()
        return response.data, None
    except Exception as e:
        return None, f"Erro ao buscar ações: {str(e)}"


def get_pending_actions(action_type: str = None) -> tuple:
    """
    Busca ações pendentes (resultado = 'pendente').
    
    Args:
        action_type: Opcional - 'mensagem' ou 'ligacao' para filtrar
    
    Returns:
        Tuple[list, Optional[str]]: (lista_de_acoes_pendentes, erro)
    """
    try:
        query = supabase.table('acoes').select('*, clientes(*)').eq('resultado', 'pendente')
        if action_type:
            query = query.eq('tipo', action_type)
        response = query.order('data', desc=True).execute()
        return response.data, None
    except Exception as e:
        return None, f"Erro ao buscar ações pendentes: {str(e)}"


def update_action_result(action_id: int, resultado: str) -> tuple:
    """
    Atualiza o resultado de uma ação.
    
    Args:
        action_id: ID da ação
        resultado: 'sim', 'nao', 'sem_resposta', 'agendou', 'comprou'
    
    Returns:
        Tuple[dict, Optional[str]]: (acao_atualizada, erro)
    """
    try:
        response = supabase.table('acoes').update({
            'resultado': resultado
        }).eq('id', action_id).execute()
        
        if response.data:
            return response.data[0], None
        else:
            return None, "Ação não encontrada"
    except Exception as e:
        return None, f"Erro ao atualizar ação: {str(e)}"


def get_clients_needing_action(days_after_purchase: int = 7) -> tuple:
    """
    Busca clientes que precisam de ação baseado na data da primeira compra.
    
    Args:
        days_after_purchase: Número de dias após a compra para disparar ação
    
    Returns:
        Tuple[list, Optional[str]]: (lista_de_clientes, erro)
    """
    try:
        from datetime import datetime, timedelta
        # Calcula a data limite (hoje - days_after_purchase)
        data_limite = (datetime.now() - timedelta(days=days_after_purchase)).date()
        
        # Busca clientes que:
        # 1. Têm data_primeira_compra
        # 2. A data_primeira_compra + days_after_purchase <= hoje
        # 3. Não têm próxima_acao agendada OU próxima_acao <= hoje
        # Seleciona clientes cuja data_primeira_compra <= data_limite (compras antigas)
        response = supabase.table('clientes').select('*').lte('data_primeira_compra', str(data_limite)).execute()
        
        # Filtra clientes que realmente precisam de ação
        clientes_que_precisam = []
        hoje = datetime.now().date()
        
        for cliente in response.data:
            data_compra_str = cliente.get('data_primeira_compra')
            if not data_compra_str:
                continue
                
            # Converte string para date
            if isinstance(data_compra_str, str):
                try:
                    # tenta ISO first
                    data_compra = datetime.fromisoformat(data_compra_str.replace('Z', '+00:00')).date()
                except Exception:
                    # tenta dd/mm/YYYY
                    try:
                        from datetime import datetime as _dt
                        data_compra = _dt.strptime(data_compra_str, '%d/%m/%Y').date()
                    except Exception:
                        continue
            else:
                data_compra = data_compra_str
            
            # Verifica se já passou o intervalo
            dias_desde_compra = (hoje - data_compra).days
            if dias_desde_compra >= days_after_purchase:
                proxima_acao = cliente.get('proxima_acao')
                if not proxima_acao:
                    clientes_que_precisam.append(cliente)
                else:
                    try:
                        pa_date = datetime.fromisoformat(str(proxima_acao).replace('Z', '+00:00')).date()
                        if pa_date <= hoje:
                            clientes_que_precisam.append(cliente)
                    except Exception:
                        # se não conseguiu parsear, considera que precisa de atenção
                        clientes_que_precisam.append(cliente)
        
        return clientes_que_precisam, None
    except Exception as e:
        return None, f"Erro ao buscar clientes que precisam de ação: {str(e)}"


def update_client_next_action(client_id: int, proxima_acao: str) -> tuple:
    """
    Atualiza a próxima ação programada de um cliente.
    
    Args:
        client_id: ID do cliente
        proxima_acao: Data/hora da próxima ação (ISO format)
    
    Returns:
        Tuple[dict, Optional[str]]: (cliente_atualizado, erro)
    """
    try:
        response = supabase.table('clientes').update({
            'proxima_acao': proxima_acao,
            'ultima_acao': datetime.now().isoformat()
        }).eq('id', client_id).execute()
        
        if response.data:
            return response.data[0], None
        else:
            return None, "Cliente não encontrado"
    except Exception as e:
        return None, f"Erro ao atualizar próxima ação: {str(e)}"
