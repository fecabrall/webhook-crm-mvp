import streamlit as st
import pandas as pd
from supabase import create_client, Client
import os
from datetime import datetime, timezone

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="MVP CRM - Painel",
    page_icon="🚀",
    layout="wide"
)

# --- CONEXÃO COM SUPABASE ---
@st.cache_resource
def init_supabase():
    try:
        if "SUPABASE_URL" in st.secrets:
            url = st.secrets["SUPABASE_URL"]
            key = st.secrets["SUPABASE_KEY"]
        else:
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

# --- FUNÇÕES AUXILIARES DE FORMATAÇÃO ---
def pretty_datetime(val):
    if not val:
        return ""
    try:
        dt = pd.to_datetime(val)
        # Exibe em formato legível + timezone local
        return dt.tz_convert(None).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return str(val)

def days_since(val):
    if not val:
        return None
    try:
        dt = pd.to_datetime(val).date()
        return (datetime.now().date() - dt).days
    except Exception:
        return None

def get_table(table_name, limit=1000):
    if not supabase:
        return pd.DataFrame()
    try:
        resp = supabase.table(table_name).select("*").limit(limit).execute()
        data = resp.data or []
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro ao buscar dados de {table_name}: {e}")
        return pd.DataFrame()

# --- LAYOUT: Abas ---
st.title("🚀 Painel de Controle - MVP Automação")
tabs = st.tabs(["Visão Geral", "Enviar Webhook (form)", "Tarefas / Ações", "Logs / Auditoria"])

# ----- ABA 1: Visão Geral -----
with tabs[0]:
    st.header("📋 Visão Geral")
    df_clientes = get_table("clientes")
    if not df_clientes.empty:
        # Formata colunas de data
        for col in ["data_primeira_compra", "proxima_acao", "ultima_acao"]:
            if col in df_clientes.columns:
                df_clientes[col + "_pretty"] = df_clientes[col].apply(pretty_datetime)
        if "data_primeira_compra" in df_clientes.columns:
            df_clientes["dias_desde_compra"] = df_clientes["data_primeira_compra"].apply(days_since)
        # Indicador visual de próxima ação
        def precisa_acao(row):
            pa = row.get("proxima_acao")
            if not pa:
                return "Sem agenda"
            try:
                pa_date = pd.to_datetime(pa)
                if pa_date <= pd.Timestamp.now():
                    return "Hoje / Atrasado"
                return "Agendado"
            except Exception:
                return "Desconhecido"
        df_clientes["status_acao"] = df_clientes.apply(precisa_acao, axis=1)

        # Mostra métricas
        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Clientes", len(df_clientes))
        col2.metric("Com próxima ação hoje/atrasada", int((df_clientes['status_acao']=="Hoje / Atrasado").sum()))
        col3.metric("Sem próxima ação", int((df_clientes['status_acao']=="Sem agenda").sum()))

        # Dataframe exibido com colunas úteis
        display_cols = ["id", "nome", "telefone", "status", "data_primeira_compra_pretty",
                        "dias_desde_compra", "proxima_acao_pretty", "ultima_acao_pretty", "status_acao", "observacoes"]
        # Filtra apenas as colunas existentes
        display_cols = [c for c in display_cols if c in df_clientes.columns]
        st.dataframe(df_clientes[display_cols].rename(columns=lambda x: x.replace("_pretty", "")), use_container_width=True)
    else:
        st.info("Nenhum cliente encontrado no banco de dados ainda.")

# ----- ABA 2: Enviar Webhook (form) -----
with tabs[1]:
    st.header("📨 Enviar novo cliente (substitui Postman)")
    st.markdown("Preencha o formulário e envie para a API. Configure `API_BASE_URL` e `API_SECRET_TOKEN` em Streamlit secrets ou variáveis de ambiente.")
    with st.form("webhook_form"):
        nome = st.text_input("Nome", "")
        telefone = st.text_input("Telefone", "")
        email = st.text_input("Email (opcional)", "")
        data_compra = st.date_input("Data da primeira compra", value=None)
        procedimento = st.text_input("Procedimento", "")
        valor_pago = st.number_input("Valor pago", min_value=0.0, step=0.01, format="%.2f")
        observacoes = st.text_area("Observações", "")
        incluir_ultima_acao = st.checkbox("Incluir campo ultima_acao igual a data da compra (opcional)", value=False)
        dry_run = st.checkbox("Dry-run (não persiste no DB, devolve payload normalizado)", value=False)
        submitted = st.form_submit_button("Enviar Webhook")

    if submitted:
        import requests, json
        API_BASE = st.secrets.get("API_BASE_URL") if "API_BASE_URL" in st.secrets else os.getenv("API_BASE_URL", "http://localhost:5000")
        TOKEN = st.secrets.get("API_SECRET_TOKEN") if "API_SECRET_TOKEN" in st.secrets else os.getenv("API_SECRET_TOKEN", "")
        url = API_BASE.rstrip("/") + "/api/webhook"
        payload = {
            "nome": nome,
            "telefone": telefone,
            "email": email,
            "procedimento": procedimento,
            "valor_pago": float(valor_pago) if valor_pago else None
        }
        if data_compra:
            payload["data_primeira_compra"] = data_compra.strftime("%d/%m/%Y")
        if observacoes:
            payload["observacoes"] = observacoes
        if incluir_ultima_acao and data_compra:
            payload["ultima_acao"] = data_compra.strftime("%d/%m/%Y")

        headers = {"Content-Type": "application/json"}
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
        if dry_run:
            headers["X-Dry-Run"] = "true"

        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            st.write("URL:", url)
            st.write("Payload enviado:", payload)
            st.write("Status:", resp.status_code)
            try:
                st.json(resp.json())
            except Exception:
                st.text(resp.text)
            if resp.status_code in (200, 201):
                st.success("Enviado com sucesso")
            else:
                st.error("Erro ao enviar webhook")
        except Exception as e:
            st.error(f"Erro na requisição: {e}")

# ----- ABA 3: Tarefas / Ações -----
with tabs[2]:
    st.header("📋 Tarefas / Ações Pendentes")
    st.markdown("Lista de ações pendentes usada pelos operadores. Fonte: view `vw_acoes_pendentes`.")
    df_acoes = get_table("vw_acoes_pendentes", limit=500)
    if not df_acoes.empty:
        # Formata data
        if "data" in df_acoes.columns:
            df_acoes["data_pretty"] = df_acoes["data"].apply(pretty_datetime)
        st.dataframe(df_acoes[["id","cliente_nome","cliente_telefone","tipo","conteudo","data_pretty","tipo_descricao"]], use_container_width=True)
        st.info("Para marcar resultado, use a interface administrativa ou crie endpoints que atualizem `acoes.resultado` via API.")
    else:
        st.info("Nenhuma ação pendente encontrada.")

# ----- ABA 4: Logs / Auditoria -----
with tabs[3]:
    st.header("📜 Logs / Auditoria")
    st.markdown("Mostra os últimos registros da tabela `auditoria` para rastrear alterações.")
    df_logs = get_table("auditoria", limit=200)
    if not df_logs.empty:
        # Tenta mostrar JSONs truncados
        def short_json(x):
            try:
                s = str(x)
                return (s[:300] + "...") if len(s) > 300 else s
            except Exception:
                return str(x)
        for c in ["dados_antigos","dados_novos"]:
            if c in df_logs.columns:
                df_logs[c] = df_logs[c].apply(short_json)
        st.dataframe(df_logs[["data_operacao","tabela_afetada","operacao","id_registro","usuario","dados_novos"]], use_container_width=True)
    else:
        st.info("Nenhum log encontrado ou tabela `auditoria` não existe no projeto.")