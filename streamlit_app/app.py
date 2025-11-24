import streamlit as st
import pandas as pd
from supabase import create_client, Client
import requests
import json
import os
from datetime import datetime, timezone
from requests.exceptions import ConnectionError, RequestException

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

# --- CONFIGURAÇÕES LOCAIS ---
OUTBOX_PATH = os.path.join(os.getcwd(), "streamlit_pending_webhooks.jsonl")

# --- FUNÇÕES AUXILIARES DE FORMATAÇÃO ---
def pretty_datetime(val):
    if not val:
        return ""
    try:
        dt = pd.to_datetime(val)
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
        data = getattr(resp, "data", None) or []
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Erro ao buscar dados de {table_name}: {e}")
        return pd.DataFrame()

# --- OUTBOX E FALLBACK ---
def save_outbox(record_payload, meta=None):
    entry = {"ts": datetime.now().isoformat(), "payload": record_payload}
    if meta:
        entry["meta"] = meta
    try:
        with open(OUTBOX_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False

def try_save_to_supabase(record_payload):
    if not supabase:
        return False, "no_supabase_client"
    try:
        resp = supabase.table("clientes").insert(record_payload).execute()
        data = getattr(resp, "data", None)
        err = getattr(resp, "error", None)
        if data:
            return True, "saved_supabase"
        if err:
            return False, f"supabase_error:{err}"
        return False, "supabase_unknown"
    except Exception as e:
        return False, f"supabase_exception:{e}"

def resend_outbox_once(api_base=None, token=None):
    if not os.path.exists(OUTBOX_PATH):
        return {"processed": 0, "left": 0}
    retained = []
    processed = 0
    try:
        with open(OUTBOX_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception:
        return {"processed": 0, "left": 0}
    for ln in lines:
        try:
            rec = json.loads(ln)
            payload = rec.get("payload", {})
        except Exception:
            continue
        sent = False
        # try backend if provided
        if api_base:
            try:
                headers = {"Content-Type": "application/json"}
                if token:
                    headers["Authorization"] = f"Bearer {token}"
                r = requests.post(api_base.rstrip("/") + "/api/webhook", json=payload, headers=headers, timeout=8)
                if r.status_code in (200, 201):
                    processed += 1
                    sent = True
                else:
                    # not successful -> try supabase
                    saved, info = try_save_to_supabase(payload)
                    if saved:
                        processed += 1
                        sent = True
            except Exception:
                pass
        if not sent:
            # try direct supabase
            saved, info = try_save_to_supabase(payload)
            if saved:
                processed += 1
                sent = True
        if not sent:
            retained.append(rec)
    # rewrite leftover
    try:
        if retained:
            with open(OUTBOX_PATH, "w", encoding="utf-8") as f:
                for r in retained:
                    f.write(json.dumps(r, ensure_ascii=False) + "\n")
        else:
            os.remove(OUTBOX_PATH)
    except Exception:
        pass
    return {"processed": processed, "left": len(retained)}

# Tenta re-enviar uma vez ao iniciar (silencioso)
API_BASE_START = st.secrets.get("API_BASE_URL") if "API_BASE_URL" in st.secrets else os.getenv("API_BASE_URL", None)
API_TOKEN_START = st.secrets.get("API_SECRET_TOKEN") if "API_SECRET_TOKEN" in st.secrets else os.getenv("API_SECRET_TOKEN", None)
if API_BASE_START or supabase:
    _res = resend_outbox_once(api_base=API_BASE_START, token=API_TOKEN_START)
    if _res.get("processed", 0) > 0:
        st.info(f"{_res['processed']} registro(s) pendentes processados automaticamente.")

# --- LAYOUT: Abas ---
st.title("🚀 Painel de Controle - MVP Automação")
tabs = st.tabs(["Visão Geral", "Enviar Webhook (form)", "Tarefas / Ações", "Logs / Auditoria"])

# ----- ABA 1: Visão Geral -----
with tabs[0]:
    st.header("📋 Visão Geral")
    df_clientes = get_table("clientes")
    if not df_clientes.empty:
        for col in ["data_primeira_compra", "proxima_acao", "ultima_acao"]:
            if col in df_clientes.columns:
                df_clientes[col + "_pretty"] = df_clientes[col].apply(pretty_datetime)
        if "data_primeira_compra" in df_clientes.columns:
            df_clientes["dias_desde_compra"] = df_clientes["data_primeira_compra"].apply(days_since)
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

        col1, col2, col3 = st.columns(3)
        col1.metric("Total de Clientes", len(df_clientes))
        col2.metric("Com próxima ação hoje/atrasada", int((df_clientes['status_acao']=="Hoje / Atrasado").sum()))
        col3.metric("Sem próxima ação", int((df_clientes['status_acao']=="Sem agenda").sum()))

        display_cols = ["id", "nome", "telefone", "status", "data_primeira_compra_pretty",
                        "dias_desde_compra", "proxima_acao_pretty", "ultima_acao_pretty", "status_acao", "observacoes"]
        display_cols = [c for c in display_cols if c in df_clientes.columns]
        st.dataframe(df_clientes[display_cols].rename(columns=lambda x: x.replace("_pretty", "")), use_container_width=True)
    else:
        st.info("Nenhum cliente encontrado no banco de dados ainda.")

# ----- ABA 2: Enviar Webhook (form) -----
with tabs[1]:
    st.header("📨 Enviar novo cliente")
    st.markdown("Formulário amigável para cadastrar clientes. O sistema tentará enviar ao backend; se indisponível, salva direto no banco; se necessário, guarda localmente para reenvio automático.")
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
        submitted = st.form_submit_button("Enviar")

    if submitted:
        API_BASE = st.secrets.get("API_BASE_URL") if "API_BASE_URL" in st.secrets else os.getenv("API_BASE_URL", "http://localhost:5000")
        TOKEN = st.secrets.get("API_SECRET_TOKEN") if "API_SECRET_TOKEN" in st.secrets else os.getenv("API_SECRET_TOKEN", "")
        url = API_BASE.rstrip("/") + "/api/webhook" if API_BASE else None
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

        # 1) tenta enviar ao backend
        sent_ok = False
        if url:
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=10)
                if resp.status_code in (200, 201):
                    st.success("Cliente registrado com sucesso.")
                    sent_ok = True
                else:
                    # backend respondeu com erro -> tenta salvar direto no Supabase
                    saved, info = try_save_to_supabase(payload)
                    if saved:
                        st.success("Cliente salvo diretamente no banco (fallback).")
                        sent_ok = True
                    else:
                        save_outbox(payload, {"backend_status": resp.status_code, "backend_text": getattr(resp, "text", "") , "fallback_info": info})
                        st.warning("Recebemos seus dados. Estamos guardando e tentaremos processar em seguida.")
            except ConnectionError:
                # backend indisponível -> tenta salvar direto no Supabase
                saved, info = try_save_to_supabase(payload)
                if saved:
                    st.success("Serviço temporariamente indisponível, mas seu cliente foi salvo diretamente no banco.")
                    sent_ok = True
                else:
                    save_outbox(payload, {"error": "connection_refused", "fallback_info": info})
                    st.warning("Serviço temporariamente indisponível. Seus dados foram recebidos e serão processados em breve.")
            except RequestException:
                save_outbox(payload, {"error": "request_exception"})
                st.warning("Problema de rede. Seus dados foram salvos e serão reenviados automaticamente.")
            except Exception:
                save_outbox(payload, {"error": "unexpected"})
                st.error("Ocorreu um problema. Seus dados foram salvos com segurança e serão verificados.")
        else:
            # sem URL configurada -> tenta salvar direto no Supabase, senão outbox
            saved, info = try_save_to_supabase(payload)
            if saved:
                st.success("Cliente salvo diretamente no banco.")
            else:
                save_outbox(payload, {"error": "no_api_url", "fallback_info": info})
                st.warning("Registro salvo localmente. Configure API_BASE_URL ou verifique conexão para processar.")

        # mostrar resumo amigável e opção de copiar payload
        if sent_ok:
            st.experimental_rerun()
        else:
            with st.expander("Dados enviados (cópia)"):
                st.code(json.dumps(payload, ensure_ascii=False, indent=2))
            if os.path.exists(OUTBOX_PATH):
                st.info("Há registros pendentes. Eles serão reenviados automaticamente quando possível.")
                if st.button("Tentar reenviar pendentes agora"):
                    res = resend_outbox_once(api_base=API_BASE if API_BASE else None, token=TOKEN if TOKEN else None)
                    st.info(f"Processados: {res.get('processed',0)} · Restantes: {res.get('left',0)}")

# ----- ABA 3: Tarefas / Ações -----
with tabs[2]:
    st.header("📋 Tarefas / Ações Pendentes")
    st.markdown("Lista de ações pendentes usada pelos operadores. Fonte: view `vw_acoes_pendentes`.")
    df_acoes = get_table("vw_acoes_pendentes", limit=500)
    if not df_acoes.empty:
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