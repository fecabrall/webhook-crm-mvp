import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from datetime import datetime

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="MVP CRM - Painel",
    page_icon="🚀",
    layout="wide"
)

# --- CONEXÃO COM SUPABASE ---
# Tenta pegar dos segredos do Streamlit (Nuvem) ou do .env (Local)
@st.cache_resource
def init_supabase():
    try:
        # Prioridade: Streamlit Cloud Secrets
        if "SUPABASE_URL" in st.secrets:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        else:
            # Fallback: Ambiente Local (.env deve estar carregado ou variáveis de sistema)
            from dotenv import load_dotenv
            load_dotenv()
            url = os.getenv("SUPABASE_URL")
            key = os.getenv("SUPABASE_KEY")
        
        if not url or not key:
            st.error("❌ Erro: Variáveis do Supabase não encontradas.")
            return None
            
        return create_client(url, key)
    except Exception as e:
        st.error(f"Erro de conexão: {e}")
        return None

supabase = init_supabase()

# --- FUNÇÃO PARA BUSCAR DADOS ---
def get_data(table_name):
    if not supabase:
        return pd.DataFrame()
    try:
        # Busca todos os dados da tabela
        response = supabase.table(table_name).select("*").execute()
        data = response.data
        if data:
            return pd.DataFrame(data)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"Erro ao buscar dados de {table_name}: {e}")
        return pd.DataFrame()

# --- INTERFACE VISUAL ---
st.title("🚀 Painel de Controle - MVP Automação")
st.markdown("---")

# Carregar Dados
if supabase:
    df_clientes = get_data("clientes")
    
    # Métricas no Topo
    col1, col2, col3 = st.columns(3)
    
    total_clientes = len(df_clientes) if not df_clientes.empty else 0
    
    with col1:
        st.metric("Total de Clientes", total_clientes)
    
    with col2:
        # Exemplo de métrica calculada (se houver coluna status)
        if not df_clientes.empty and 'status' in df_clientes.columns:
            novos = len(df_clientes[df_clientes['status'].str.contains('Novo', case=False, na=False)])
            st.metric("Novos Clientes", novos)
        else:
            st.metric("Novos Clientes", 0)

    with col3:
        st.metric("Status do Sistema", "Online 🟢")

    # Tabela de Clientes
    st.subheader("📋 Base de Clientes")
    
    if not df_clientes.empty:
        # Formatação básica
        st.dataframe(
            df_clientes, 
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Nenhum cliente encontrado no banco de dados ainda.")
        
    # Botão de Atualizar
    if st.button("🔄 Atualizar Dados"):
        st.rerun()

else:
    st.warning("Conexão com Banco de Dados não estabelecida.")
