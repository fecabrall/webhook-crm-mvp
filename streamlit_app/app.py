import streamlit as st
import pandas as pd
from supabase import create_client, Client
import requests
import json
import os
from datetime import datetime, timezone, timedelta
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
    """Formata datetime para padrão brasileiro"""
    if not val:
        return ""
    try:
        dt = pd.to_datetime(val)
        return dt.tz_convert(None).strftime("%d/%m/%Y %H:%M")
    except Exception:
        return str(val)

def pretty_date(val):
    """Formata date para padrão brasileiro"""
    if not val:
        return ""
    try:
        dt = pd.to_datetime(val)
        return dt.strftime("%d/%m/%Y")
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

def resend_single_outbox_record(rec, api_base=None, token=None):
    """Try to resend a single outbox record. Returns (success, info)."""
    payload = rec.get("payload", {})
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

# --- LAYOUT: Abas ---
st.title("🚀 Painel de Controle - MVP CRM")
tabs = st.tabs(["📊 Visão Geral", "📝 Cadastro de Cliente", "✅ Tarefas Pendentes", "📥 Envios Pendentes", "📜 Auditoria"])

# ----- ABA 1: Visão Geral -----
with tabs[0]:
    st.header("📊 Visão Geral de Clientes")
    
    df_clientes = get_table("clientes")
    
    if not df_clientes.empty:
        # Formata datas
        if "data_primeira_compra" in df_clientes.columns:
            df_clientes["DATA DA PRIMEIRA COMPRA"] = df_clientes["data_primeira_compra"].apply(pretty_date)
            df_clientes["DIAS DESDE A COMPRA ANTERIOR"] = df_clientes["data_primeira_compra"].apply(days_since)
        
        if "proxima_acao" in df_clientes.columns:
            df_clientes["PRÓXIMA AÇÃO"] = df_clientes["proxima_acao"].apply(pretty_datetime)
        
        if "ultima_acao" in df_clientes.columns:
            df_clientes["ÚLTIMA AÇÃO"] = df_clientes["ultima_acao"].apply(pretty_datetime)
        
        if 'cpf' in df_clientes.columns:
            df_clientes['CPF'] = df_clientes['cpf'].apply(mask_cpf)
        
        # Define status da ação
        def precisa_acao(row):
            pa = row.get("proxima_acao")
            if not pa:
                return "Sem agenda"
            try:
                pa_date = pd.to_datetime(pa)
                if pa_date <= pd.Timestamp.now():
                    return "⚠️ Hoje/Atrasado"
                return "✅ Agendado"
            except Exception:
                return "Desconhecido"
        
        df_clientes["STATUS DA AÇÃO"] = df_clientes.apply(precisa_acao, axis=1)
        
        # Métricas
        col1, col2, col3 = st.columns(3)
        col1.metric("📊 Total de Clientes", len(df_clientes))
        col2.metric("⚠️ Ação Hoje/Atrasada", int((df_clientes['STATUS DA AÇÃO']=="⚠️ Hoje/Atrasado").sum()))
        col3.metric("📅 Sem Próxima Ação", int((df_clientes['STATUS DA AÇÃO']=="Sem agenda").sum()))
        
        st.markdown("---")
        
        # Renomeia colunas para exibição
        rename_map = {
            "id": "ID",
            "nome": "NOME",
            "telefone": "TELEFONE",
            "email": "EMAIL",
            "status": "STATUS",
            "procedimento": "PROCEDIMENTO",
            "valor_pago": "VALOR PAGO",
            "observacoes": "OBSERVAÇÕES"
        }
        
        # Seleciona colunas para exibir
        display_cols = ["ID", "NOME", "CPF", "TELEFONE", "EMAIL", "STATUS", 
                       "DATA DA PRIMEIRA COMPRA", "DIAS DESDE A COMPRA ANTERIOR",
                       "PROCEDIMENTO", "VALOR PAGO", "PRÓXIMA AÇÃO", "ÚLTIMA AÇÃO", 
                       "STATUS DA AÇÃO", "OBSERVAÇÕES"]
        
        # Remove colunas que não existem
        display_cols = [c for c in display_cols if c in df_clientes.columns]
        
        # Renomeia colunas originais
        for old, new in rename_map.items():
            if old in df_clientes.columns:
                df_clientes[new] = df_clientes[old]
        
        st.dataframe(
            df_clientes[display_cols],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("ℹ️ Nenhum cliente encontrado no banco de dados ainda.")

# ----- ABA 2: Cadastro de Cliente -----
with tabs[1]:
    st.header("📝 Cadastro de Cliente")
    
    # Tipo de cadastro
    tipo_cadastro = st.radio(
        "Tipo de cadastro:",
        ("🆕 Novo Cliente", "👤 Cliente Existente"),
        horizontal=True
    )
    
    # Inicializa dados do formulário
    if 'form_data' not in st.session_state:
        st.session_state.form_data = {}
    
    # Para cliente existente - busca por CPF
    if tipo_cadastro == "👤 Cliente Existente":
        st.markdown("### 🔍 Buscar Cliente por CPF")
        col_search, col_btn = st.columns([3, 1])
        
        with col_search:
            cpf_busca = st.text_input(
                "CPF (apenas números)",
                placeholder="12345678901",
                key="cpf_search"
            )
        
        with col_btn:
            st.markdown("<br>", unsafe_allow_html=True)
            buscar = st.button("🔍 Buscar", use_container_width=True)
        
        if buscar and cpf_busca:
            from utils.validators import sanitize_cpf, validate_cpf
            cpf_digits = sanitize_cpf(cpf_busca)
            ok, err = validate_cpf(cpf_digits)
            
            if not ok:
                st.error(f"❌ CPF inválido: {err}")
            else:
                try:
                    resp = supabase.table('clientes').select('*').eq('cpf', cpf_digits).limit(1).execute()
                    data = getattr(resp, 'data', None) or []
                    
                    if data:
                        st.session_state.form_data = data[0]
                        st.success(f"✅ Cliente encontrado: {data[0].get('nome')}")
                    else:
                        st.warning("⚠️ Cliente não encontrado. Preencha os dados manualmente.")
                        st.session_state.form_data = {'cpf': cpf_digits}
                except Exception as e:
                    st.error(f"❌ Erro na busca: {e}")
        
        st.markdown("---")
    
    # Formulário de cadastro
    with st.form("cadastro_form", clear_on_submit=False):
        st.markdown("### 📋 Dados do Cliente")
        
        # Dados do formulário preenchidos se existirem
        form_data = st.session_state.form_data
        
        col1, col2 = st.columns(2)
        
        with col1:
            nome = st.text_input(
                "Nome *",
                value=form_data.get("nome", ""),
                placeholder="João"
            )
            
            telefone = st.text_input(
                "Telefone *",
                value=form_data.get("telefone", ""),
                placeholder="11999999999"
            )
            
            cpf = st.text_input(
                "CPF *",
                value=form_data.get("cpf", ""),
                placeholder="12345678901"
            )
            
            data_compra = st.date_input(
                "Data da Compra *" if tipo_cadastro == "👤 Cliente Existente" else "Data da 1ª Compra *",
                value=None
            )
        
        with col2:
            sobrenome = st.text_input(
                "Sobrenome *",
                value=form_data.get("sobrenome", ""),
                placeholder="Silva"
            )
            
            email = st.text_input(
                "Email",
                value=form_data.get("email", ""),
                placeholder="joao.silva@email.com"
            )
            
            procedimento = st.text_input(
                "Procedimento",
                value=form_data.get("procedimento", ""),
                placeholder="Consulta, limpeza, etc."
            )
            
            valor_pago = st.number_input(
                "Valor Pago (R$)",
                min_value=0.0,
                step=0.01,
                format="%.2f",
                value=float(form_data.get("valor_pago", 0.0))
            )
        
        # Status
        status_options = [
            "Novo Cliente - 1ª compra",
            "Cliente Recorrente",
            "Em Acompanhamento",
            "Inativo",
            "Outro..."
        ]
        
        status_sel = st.selectbox(
            "Status",
            status_options,
            index=0
        )
        
        if status_sel == "Outro...":
            status_custom = st.text_input(
                "Especifique o status:",
                placeholder="Ex: Cliente VIP, Aguardando retorno, etc."
            )
            status = status_custom if status_custom else "Outro"
        else:
            status = status_sel
        
        # Observações
        observacoes = st.text_area(
            "Observações",
            value=form_data.get("observacoes", ""),
            placeholder="Informações adicionais sobre o cliente..."
        )
        
        st.markdown("---")
        st.markdown("### 📅 Agendamento")
        
        agendar_proxima = st.checkbox("Definir próxima ação manualmente")
        proxima_acao_dt = None
        
        if agendar_proxima:
            col_data, col_hora = st.columns(2)
            with col_data:
                proxima_data = st.date_input("Data da próxima ação", value=None)
            with col_hora:
                proxima_hora = st.time_input("Horário", value=None)
            
            if proxima_data and proxima_hora:
                proxima_acao_dt = datetime.combine(proxima_data, proxima_hora)
        
        st.markdown("---")
        st.markdown("### ⚡ Ações Imediatas")
        
        criar_acao = st.checkbox("Criar ação agora para este cliente")
        acao_tipo = None
        acao_conteudo = None
        acao_resultado = "pendente"
        
        if criar_acao:
            col_tipo, col_resultado = st.columns(2)
            
            with col_tipo:
                acao_tipo = st.selectbox(
                    "Tipo de ação",
                    ("📞 Ligação", "💬 Mensagem"),
                    format_func=lambda x: x
                )
                acao_tipo = "ligacao" if "Ligação" in acao_tipo else "mensagem"
            
            with col_resultado:
                acao_resultado = st.selectbox(
                    "Status inicial",
                    [
                        ("⏳ Pendente", "pendente"),
                        ("✅ Realizado", "sim"),
                        ("❌ Não atendeu", "sem_resposta"),
                        ("📅 Agendou", "agendou"),
                        ("💰 Comprou", "comprou")
                    ],
                    format_func=lambda x: x[0]
                )[1]
            
            acao_conteudo = st.text_area(
                "Observações da ação",
                placeholder="Descreva o que foi feito ou planejado..."
            )
        
        st.markdown("---")
        
        # Botão de envio
        col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])
        
        with col_btn1:
            submitted = st.form_submit_button(
                "✅ Cadastrar Cliente",
                use_container_width=True,
                type="primary"
            )
        
        with col_btn2:
            limpar = st.form_submit_button(
                "🗑️ Limpar",
                use_container_width=True
            )
        
        if limpar:
            st.session_state.form_data = {}
            st.rerun()
    
    if submitted:
        # Validação básica
        if not nome or not sobrenome or not telefone or not cpf:
            st.error("❌ Por favor, preencha todos os campos obrigatórios (*).")
        else:
            # Monta o payload
            nome_completo = f"{nome} {sobrenome}"
            
            from utils.validators import sanitize_cpf, validate_cpf, sanitize_phone, validate_phone
            
            cpf_digits = sanitize_cpf(cpf)
            cpf_ok, cpf_err = validate_cpf(cpf_digits)
            
            if not cpf_ok:
                st.error(f"❌ CPF inválido: {cpf_err}")
            else:
                telefone_limpo = sanitize_phone(telefone)
                tel_ok, tel_err = validate_phone(telefone_limpo)
                
                if not tel_ok:
                    st.error(f"❌ Telefone inválido: {tel_err}")
                else:
                    payload = {
                        "nome": nome_completo,
                        "telefone": telefone_limpo,
                        "email": email if email else None,
                        "cpf": cpf_digits,
                        "status": status,
                        "procedimento": procedimento if procedimento else None,
                        "valor_pago": float(valor_pago) if valor_pago else None,
                        "observacoes": observacoes if observacoes else None
                    }
                    
                    if data_compra:
                        payload["data_primeira_compra"] = data_compra.strftime("%Y-%m-%d")
                    
                    if proxima_acao_dt:
                        payload["proxima_acao"] = proxima_acao_dt.isoformat()
                    
                    agora_iso = datetime.now().isoformat()
                    if criar_acao:
                        payload["ultima_acao"] = agora_iso
                    
                    # Tenta salvar
                    saved, info, rec = try_insert_client_supabase(payload)
                    
                    if saved:
                        st.success(f"✅ Cliente {nome_completo} cadastrado com sucesso!")
                        
                        # Cria ação se solicitado
                        if criar_acao and rec:
                            action_payload = {
                                "id_cliente": rec.get("id"),
                                "tipo": acao_tipo,
                                "conteudo": acao_conteudo,
                                "data": agora_iso,
                                "resultado": acao_resultado
                            }
                            
                            a_saved, a_info, a_rec = try_insert_action_supabase(action_payload)
                            
                            if a_saved:
                                st.success("✅ Ação criada com sucesso!")
                        
                        # Limpa o formulário
                        st.session_state.form_data = {}
                        st.balloons()
                    else:
                        st.error(f"❌ Erro ao cadastrar cliente: {info}")
                        save_outbox(payload)

# ----- ABA 3: Tarefas Pendentes -----
with tabs[2]:
    st.header("✅ Tarefas e Ações Pendentes")
    
    df_acoes = get_table("vw_acoes_pendentes", limit=500)
    
    if not df_acoes.empty:
        if "data" in df_acoes.columns:
            df_acoes["DATA/HORA"] = df_acoes["data"].apply(pretty_datetime)
        
        # Renomeia colunas
        rename_map = {
            "id": "ID",
            "cliente_nome": "CLIENTE",
            "cliente_telefone": "TELEFONE",
            "tipo": "TIPO",
            "conteudo": "DESCRIÇÃO",
            "tipo_descricao": "STATUS"
        }
        
        for old, new in rename_map.items():
            if old in df_acoes.columns:
                df_acoes[new] = df_acoes[old]
        
        # Adiciona ícones ao tipo
        def formata_tipo(tipo):
            if tipo == "mensagem":
                return "💬 Mensagem"
            elif tipo == "ligacao":
                return "📞 Ligação"
            return tipo
        
        if "TIPO" in df_acoes.columns:
            df_acoes["TIPO"] = df_acoes["TIPO"].apply(formata_tipo)
        
        st.dataframe(
            df_acoes[["ID", "CLIENTE", "TELEFONE", "TIPO", "DESCRIÇÃO", "DATA/HORA", "STATUS"]],
            use_container_width=True,
            hide_index=True
        )
        
        st.info("💡 **Dica:** Para atualizar o resultado de uma ação, use a API ou adicione controles aqui.")
    else:
        st.success("🎉 Nenhuma ação pendente! Você está em dia com as tarefas.")

# ----- ABA 4: Envios Pendentes -----
with tabs[3]:
    st.header("📥 Envios Pendentes (Outbox)")
    
    if not os.path.exists(OUTBOX_PATH):
        st.success("✅ Nenhum envio pendente. Todos os dados foram sincronizados!")
    else:
        try:
            with open(OUTBOX_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()
        except Exception as e:
            st.error(f"❌ Erro ao ler outbox: {e}")
            lines = []
        
        if lines:
            st.warning(f"⚠️ Existem {len(lines)} envio(s) pendente(s) aguardando sincronização.")
            
            for i, ln in enumerate(lines):
                try:
                    rec = json.loads(ln)
                except Exception:
                    rec = {"ts": "?", "payload": {}}
                
                ts = rec.get("ts", "?")
                payload = rec.get("payload", {})
                nome = payload.get('nome', payload.get('telefone', 'Desconhecido'))
                
                with st.expander(f"📋 Envio #{i+1} - {nome} ({ts})", expanded=False):
                    st.json(payload)
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if st.button(f"🔄 Reenviar", key=f"resend_{i}"):
                            api_base = st.secrets.get("API_BASE_URL") if "API_BASE_URL" in st.secrets else os.getenv("API_BASE_URL", None)
                            token = st.secrets.get("API_SECRET_TOKEN") if "API_SECRET_TOKEN" in st.secrets else os.getenv("API_SECRET_TOKEN", None)
                            
                            ok, info = resend_single_outbox_record(rec, api_base=api_base, token=token)
                            
                            if ok:
                                removed = remove_outbox_entry_by_index(i)
                                if removed:
                                    st.success("✅ Reenviado e removido dos pendentes!")
                                    st.rerun()
                                else:
                                    st.success("✅ Reenviado com sucesso!")
                            else:
                                st.error(f"❌ Falha ao reenviar: {info}")
                    
                    with col2:
                        if st.button(f"🗑️ Remover", key=f"delete_{i}"):
                            removed = remove_outbox_entry_by_index(i)
                            if removed:
                                st.success("✅ Item removido!")
                                st.rerun()
                            else:
                                st.error("❌ Erro ao remover item.")

# ----- ABA 5: Auditoria -----
with tabs[4]:
    st.header("📜 Logs de Auditoria")
    
    df_logs = get_table("auditoria", limit=200)
    
    if not df_logs.empty:
        if "data_operacao" in df_logs.columns:
            df_logs["DATA/HORA"] = df_logs["data_operacao"].apply(pretty_datetime)
        
        # Função para encurtar JSON
        def short_json(x):
            try:
                s = str(x)
                return (s[:100] + "...") if len(s) > 100 else s
            except Exception:
                return str(x)
        
        for c in ["dados_antigos", "dados_novos"]:
            if c in df_logs.columns:
                df_logs[c + "_short"] = df_logs[c].apply(short_json)
        
        # Renomeia colunas
        rename_map = {
            "tabela_afetada": "TABELA",
            "operacao": "OPERAÇÃO",
            "id_registro": "ID REGISTRO",
            "usuario": "USUÁRIO"
        }
        
        for old, new in rename_map.items():
            if old in df_logs.columns:
                df_logs[new] = df_logs[old]
        
        # Adiciona cores às operações
        def formata_operacao(op):
            if op == "INSERT":
                return "➕ INSERT"
            elif op == "UPDATE":
                return "✏️ UPDATE"
            elif op == "DELETE":
                return "🗑️ DELETE"
            return op
        
        if "OPERAÇÃO" in df_logs.columns:
            df_logs["OPERAÇÃO"] = df_logs["OPERAÇÃO"].apply(formata_operacao)
        
        st.dataframe(
            df_logs[["DATA/HORA", "TABELA", "OPERAÇÃO", "ID REGISTRO", "USUÁRIO", "dados_novos_short"]].rename(columns={"dados_novos_short": "DADOS"}),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("ℹ️ Nenhum log de auditoria encontrado ou tabela 'auditoria' não existe.")

# --- FOOTER ---
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666; padding: 20px;'>
        <p>🚀 <b>MVP CRM & Automação</b> | Desenvolvido com ❤️ usando Streamlit</p>
        <p style='font-size: 0.8em;'>© 2025 - Todos os direitos reservados</p>
    </div>
    """,
    unsafe_allow_html=True
)