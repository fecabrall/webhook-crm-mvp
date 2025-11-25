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


def mask_cpf(cpf: str) -> str:
    if not cpf:
        return ""
    s = ''.join([c for c in str(cpf) if c.isdigit()])
    if len(s) != 11:
        return s
    return f"{s[0:3]}.{s[3:6]}.{s[6:9]}-{s[9:11]}"

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

def try_insert_client_supabase(record_payload):
    """Insere cliente no Supabase e retorna (success, info, record_or_none)"""
    if not supabase:
        return False, "no_supabase_client", None
    try:
        resp = supabase.table("clientes").insert(record_payload).execute()
        data = getattr(resp, "data", None)
        err = getattr(resp, "error", None)
        if data:
            return True, "saved_supabase", data[0]
        if err:
            return False, f"supabase_error:{err}", None
        return False, "supabase_unknown", None
    except Exception as e:
        return False, f"supabase_exception:{e}", None


def try_insert_action_supabase(action_payload):
    """Insere ação na tabela 'acoes' e retorna (success, info, record_or_none)"""
    if not supabase:
        return False, "no_supabase_client", None
    try:
        resp = supabase.table("acoes").insert(action_payload).execute()
        data = getattr(resp, "data", None)
        err = getattr(resp, "error", None)
        if data:
            return True, "saved_action", data[0]
        if err:
            return False, f"supabase_error:{err}", None
        return False, "supabase_unknown", None
    except Exception as e:
        return False, f"supabase_exception:{e}", None

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


def resend_single_outbox_record(rec, api_base=None, token=None):
    """Try to resend a single outbox record. Returns (success, info)."""
    payload = rec.get("payload", {})
    # try backend first
    if api_base:
        try:
            headers = {"Content-Type": "application/json"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            r = requests.post(api_base.rstrip("/") + "/api/webhook", json=payload, headers=headers, timeout=8)
            if r.status_code in (200, 201):
                return True, "sent_backend"
        except Exception:
            pass

    # try direct supabase
    saved, info, rec_saved = try_insert_client_supabase(payload)
    if saved:
        return True, f"saved_supabase:{rec_saved.get('id') if rec_saved else ''}"

    return False, info


def remove_outbox_entry_by_index(idx):
    """Remove a single outbox entry by its index (0-based)."""
    if not os.path.exists(OUTBOX_PATH):
        return False
    try:
        with open(OUTBOX_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if idx < 0 or idx >= len(lines):
            return False
        del lines[idx]
        if lines:
            with open(OUTBOX_PATH, "w", encoding="utf-8") as f:
                f.writelines(lines)
        else:
            os.remove(OUTBOX_PATH)
        return True
    except Exception:
        return False

# Tenta re-enviar uma vez ao iniciar (silencioso)
API_BASE_START = st.secrets.get("API_BASE_URL") if "API_BASE_URL" in st.secrets else os.getenv("API_BASE_URL", None)
API_TOKEN_START = st.secrets.get("API_SECRET_TOKEN") if "API_SECRET_TOKEN" in st.secrets else os.getenv("API_SECRET_TOKEN", None)
if API_BASE_START or supabase:
    _res = resend_outbox_once(api_base=API_BASE_START, token=API_TOKEN_START)
    if _res.get("processed", 0) > 0:
        st.info(f"{_res['processed']} registro(s) pendentes processados automaticamente.")

# --- LAYOUT: Abas ---
st.title("🚀 Painel de Controle - MVP Automação")
tabs = st.tabs(["Visão Geral", "Enviar Webhook (form)", "Tarefas / Ações", "Pendentes / Outbox", "Logs / Auditoria"])

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
        # format cpf for display (masked)
        if 'cpf' in df_clientes.columns:
            df_clientes['cpf_pretty'] = df_clientes['cpf'].apply(mask_cpf)
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

        display_cols = ["id", "nome", "cpf_pretty", "telefone", "status", "data_primeira_compra_pretty",
                "dias_desde_compra", "proxima_acao_pretty", "ultima_acao_pretty", "status_acao", "observacoes"]
        display_cols = [c for c in display_cols if c in df_clientes.columns]
        st.dataframe(df_clientes[display_cols].rename(columns=lambda x: x.replace("_pretty", "")), use_container_width=True)
    else:
        st.info("Nenhum cliente encontrado no banco de dados ainda.")

# ----- ABA 2: Enviar Webhook (form) -----
with tabs[1]:
    st.header("📨 Enviar novo cliente")
    st.markdown("Formulário amigável para cadastrar clientes. O sistema tentará enviar ao backend; se indisponível, salva direto no banco; se necessário, guarda localmente para reenvio automático.")
    # Tipo de cliente e busca por CPF (fora do form para autocomplete)
    cliente_tipo = st.radio("Tipo de cliente", ("Novo", "Existente"), index=0, horizontal=True)
    cpf_search = None
    prefill = st.session_state.get("prefill_client", {})
    if cliente_tipo == "Existente":
        cols_search = st.columns([2,1])
        cpf_search = cols_search[0].text_input("CPF (apenas números)", value=prefill.get("cpf",""))
        if cols_search[1].button("Buscar por CPF"):
            from utils.validators import sanitize_cpf, validate_cpf
            cpf_digits = sanitize_cpf(cpf_search)
            ok, err = validate_cpf(cpf_digits)
            if not ok:
                st.error(f"CPF inválido: {err}")
            else:
                # procura no Supabase por cpf
                try:
                    resp = supabase.table('clientes').select('*').eq('cpf', cpf_digits).limit(1).execute()
                    data = getattr(resp, 'data', None) or []
                    if data:
                        client = data[0]
                        st.session_state['prefill_client'] = client
                        st.experimental_rerun()
                    else:
                        st.info("Cliente não encontrado. Preencha os dados manualmente.")
                except Exception as e:
                    st.error(f"Erro na busca: {e}")

    with st.form("webhook_form"):
        # prefill values if present
        nome = st.text_input("Nome completo", value=prefill.get("nome",""))
        telefone = st.text_input("Telefone", value=prefill.get("telefone",""))
        email = st.text_input("Email (opcional)", value=prefill.get("email",""))

        status_options = ["Novo Cliente - 1 compra", "Em follow-up", "Recorrente", "Perdido", "Outro..."]
        status_sel = st.selectbox("Status (padrões)", status_options, index=0)
        if status_sel == "Outro...":
            status = st.text_input("Status personalizado")
        else:
            status = status_sel

        # Data label changes for novo/existente
        if cliente_tipo == "Novo":
            data_compra = st.date_input("Data da primeira compra", value=None)
        else:
            data_compra = st.date_input("Data desta compra", value=None)
        procedimento = st.text_input("Procedimento", "")
        valor_pago = st.number_input("Valor pago", min_value=0.0, step=0.01, format="%.2f")
        observacoes = st.text_area("Observações", value=prefill.get("observacoes",""))

        # show CPF in form for existing as read-only if prefilled
        if cliente_tipo == "Existente":
            cpf_display = prefill.get('cpf', cpf_search or "")
            st.text_input("CPF (identificador)", value=cpf_display, disabled=True)

        st.markdown("---")
        st.subheader("Agendamento")
        proxima_manual = st.checkbox("Definir próxima ação manualmente")
        proxima_acao_dt = None
        if proxima_manual:
            proxima_acao_dt = st.datetime_input("Próxima ação (data e hora)", value=None)

        st.markdown("---")
        st.subheader("Ações imediatas (opcional)")
        criar_acao = st.checkbox("Criar ação agora para este cliente")
        acao_tipo = None
        acao_conteudo = None
        acao_resultado = "pendente"
        if criar_acao:
            acao_tipo = st.selectbox("Tipo de ação", ("ligacao", "mensagem"))
            acao_conteudo = st.text_area("Conteúdo / Observações da ação")
            acao_resultado = st.selectbox("Resultado inicial", ("pendente", "sem_resposta", "agendou", "comprou", "sim", "nao"), index=0)

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
            "status": status or "Novo Cliente - 1 compra",
            "procedimento": procedimento,
            "valor_pago": float(valor_pago) if valor_pago else None,
            "observacoes": observacoes
        }

        # include cpf when available
        cpf_field = prefill.get('cpf') if prefill.get('cpf') else (cpf_search or None)
        # validate CPF if present (existing clients require valid CPF)
        validation_failed = False
        if cpf_field:
            from utils.validators import sanitize_cpf, validate_cpf
            cpf_digits = sanitize_cpf(cpf_field)
            ok, err = validate_cpf(cpf_digits)
            if not ok:
                st.error(f"CPF inválido: {err}")
                validation_failed = True
        if cpf_field:
            from utils.validators import sanitize_cpf
            payload['cpf'] = sanitize_cpf(cpf_field)

        if data_compra:
            payload["data_primeira_compra"] = data_compra.strftime("%d/%m/%Y")

        if proxima_acao_dt:
            try:
                payload["proxima_acao"] = proxima_acao_dt.isoformat()
            except Exception:
                payload["proxima_acao"] = None

        # Se o usuário marcou criar ação agora, iremos tentar criar ação e atualizar ultima_acao
        agora_iso = datetime.now().isoformat()
        if criar_acao and not dry_run:
            # marca que houve uma ação agora
            payload["ultima_acao"] = agora_iso

        headers = {"Content-Type": "application/json"}
        if TOKEN:
            headers["Authorization"] = f"Bearer {TOKEN}"
        if dry_run:
            headers["X-Dry-Run"] = "true"

        # Envio/fluxo
        client_saved = False
        client_record = None
        client_id = None

        # 1) tenta enviar ao backend
        if validation_failed:
            st.warning("Corrija o CPF antes de enviar.")
        else:
            # dry-run path
            if dry_run:
                st.json({"dry_run": True, "normalized_payload": payload})
                client_saved = False
            # try backend when configured
            elif url and not dry_run:
                try:
                    resp = requests.post(url, json=payload, headers=headers, timeout=10)
                    if resp.status_code in (200, 201):
                        client_saved = True
                        try:
                            j = resp.json()
                            client_id = j.get("client_id")
                        except Exception:
                            client_id = None
                    else:
                        # backend respondeu com erro -> tenta salvar direto no Supabase
                        saved, info, rec = try_insert_client_supabase(payload)
                        if saved:
                            client_saved = True
                            client_record = rec
                            client_id = rec.get("id") if rec else None
                        else:
                            save_outbox(payload, {"backend_status": resp.status_code, "backend_text": getattr(resp, "text", ""), "fallback_info": info})
                            st.warning("Recebemos seus dados. Estamos guardando e tentaremos processar em seguida.")
                except ConnectionError:
                    # backend indisponível -> tenta salvar direto no Supabase
                    saved, info, rec = try_insert_client_supabase(payload)
                    if saved:
                        client_saved = True
                        client_record = rec
                        client_id = rec.get("id") if rec else None
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
                # sem URL configurada -> tenta salvar direto no Supabase
                saved, info, rec = try_insert_client_supabase(payload)
                if saved:
                    client_saved = True
                    client_record = rec
                    client_id = rec.get("id") if rec else None
                else:
                    save_outbox(payload, {"error": "no_api_url", "fallback_info": info})
                    st.warning("Registro salvo localmente. Configure API_BASE_URL ou verifique conexão para processar.")

        # Se foi criado/registrado com sucesso e o usuário pediu ação imediata, cria a ação
        action_created = False
        if client_saved and criar_acao and not dry_run:
            action_payload = {
                "id_cliente": client_id,
                "tipo": acao_tipo,
                "conteudo": acao_conteudo,
                "data": agora_iso,
                "resultado": acao_resultado
            }
            a_saved, a_info, a_rec = try_insert_action_supabase(action_payload)
            if a_saved:
                action_created = True
                # atualiza ultima_acao do cliente se tivermos id
                try:
                    if client_id:
                        supabase.table('clientes').update({'ultima_acao': agora_iso}).eq('id', client_id).execute()
                except Exception:
                    pass

        # If existing client and user filled a "data desta compra", create a purchase action and update client summary
        if client_saved and cliente_tipo == "Existente" and data_compra and not dry_run:
            try:
                dt_str = data_compra.strftime('%Y-%m-%d')
            except Exception:
                dt_str = None
            purchase_content = f"Procedimento: {procedimento} | Valor: {valor_pago} | Data: {dt_str}"
            purchase_action = {
                'id_cliente': client_id,
                'tipo': 'compra',
                'conteudo': purchase_content,
                'data': agora_iso,
                'resultado': 'comprou'
            }
            try:
                try_insert_action_supabase(purchase_action)
            except Exception:
                pass
            # update cliente resumo (procedimento, valor_pago, ultima_acao)
            try:
                upd = {}
                if procedimento:
                    upd['procedimento'] = procedimento
                if valor_pago:
                    upd['valor_pago'] = float(valor_pago)
                upd['ultima_acao'] = agora_iso
                if upd and client_id:
                    supabase.table('clientes').update(upd).eq('id', client_id).execute()
            except Exception:
                pass

        # Feedback amigável
        if client_saved:
            msg = "Cliente registrado com sucesso."
            if action_created:
                msg += " Ação criada."
            st.success(msg)
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

# ----- ABA 4: Pendentes / Outbox -----
with tabs[3]:
    st.header("📥 Pendentes / Outbox")
    st.markdown("Lista de envios locais que não foram processados. Você pode reenviar individualmente ao backend ou remover entradas.")
    if not os.path.exists(OUTBOX_PATH):
        st.info("Nenhum item pendente encontrado.")
    else:
        try:
            with open(OUTBOX_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            st.error(f"Erro ao ler outbox: {e}")
            lines = []

        for i, ln in enumerate(lines):
            try:
                rec = json.loads(ln)
            except Exception:
                rec = {"ts": "?", "payload": {}}
            ts = rec.get("ts", "?")
            payload = rec.get("payload", {})
            title = f"{i} — {ts} — {payload.get('nome', payload.get('telefone',''))}"
            with st.expander(title, expanded=False):
                st.json(payload)
                cols = st.columns([1,1,1])
                if cols[0].button(f"Reenviar {i}"):
                    api_base = st.secrets.get("API_BASE_URL") if "API_BASE_URL" in st.secrets else os.getenv("API_BASE_URL", None)
                    token = st.secrets.get("API_SECRET_TOKEN") if "API_SECRET_TOKEN" in st.secrets else os.getenv("API_SECRET_TOKEN", None)
                    ok, info = resend_single_outbox_record(rec, api_base=api_base, token=token)
                    if ok:
                        removed = remove_outbox_entry_by_index(i)
                        if removed:
                            st.success("Reenviado e removido dos pendentes.")
                        else:
                            st.success("Reenviado; não foi possível remover o item local (verifique permissões).")
                        st.experimental_rerun()
                    else:
                        st.error(f"Falha ao reenviar: {info}")
                if cols[1].button(f"Apagar {i}"):
                    removed = remove_outbox_entry_by_index(i)
                    if removed:
                        st.success("Item removido do outbox.")
                        st.experimental_rerun()
                    else:
                        st.error("Falha ao remover o item.")
                if cols[2].button(f"Salvar como arquivo {i}"):
                    # export payload as file
                    fn = f"pending_{i}.json"
                    try:
                        with open(fn, "w", encoding="utf-8") as f:
                            json.dump(payload, f, ensure_ascii=False, indent=2)
                        st.success(f"Salvo em {fn}")
                    except Exception as e:
                        st.error(f"Erro ao salvar arquivo: {e}")

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