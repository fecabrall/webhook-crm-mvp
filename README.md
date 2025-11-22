# 🚀 MVP CRM - Automação de Vendas

Um sistema completo de CRM (Customer Relationship Management) para automação de vendas, construído para capturar leads de webhooks externos (simulando sistemas de chat/WhatsApp) e processá-los em tempo real, apresentando os dados em um painel de controle interativo.

## 📋 Índice

- [Sobre o Projeto](#sobre-o-projeto)
- [Arquitetura](#arquitetura)
- [Tecnologias](#tecnologias)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Uso](#uso)
- [Deploy](#deploy)
- [API Endpoints](#api-endpoints)
- [Melhorias Futuras](#melhorias-futuras)

## 🎯 Sobre o Projeto

Este MVP foi desenvolvido para demonstrar um fluxo completo de automação de vendas:

1. **Captura de Leads**: Recebe dados de clientes via webhook de sistemas externos
2. **Processamento**: Valida, sanitiza e armazena os dados no banco
3. **Visualização**: Painel em tempo real para acompanhamento dos clientes
4. **Automação**: Sistema agendado para processar e enviar mensagens de acompanhamento

### Fluxo de Trabalho

```
Sistema Externo → Webhook → API Flask → Supabase → Dashboard Streamlit
                                              ↓
                                    Scheduler (Automação Diária)
```

## 🏗️ Arquitetura

O sistema é dividido em três camadas principais:

### Camada 1: Backend (API Flask)
- **Responsabilidade**: Recebe requisições POST via webhook e executa tarefas agendadas
- **Arquivos**: `app.py`, `routes/webhooks.py`, `services/scheduler.py`
- **Deploy**: Render.com

### Camada 2: Banco de Dados
- **Responsabilidade**: Armazenamento centralizado de dados
- **Tecnologia**: Supabase (PostgreSQL)
- **Tabela Principal**: `clientes`

### Camada 3: Frontend (Dashboard)
- **Responsabilidade**: Visualização de dados em tempo real
- **Arquivo**: `streamlit_app/app.py`
- **Deploy**: Streamlit Cloud

## 🛠️ Tecnologias

### Backend
- **Python 3.11.9** (versão obrigatória para compatibilidade)
- **Flask 3.0.0** - Framework web para API
- **Gunicorn** - Servidor WSGI para produção
- **APScheduler 3.10.4** - Agendamento de tarefas

### Banco de Dados
- **Supabase 2.5.0** - PostgreSQL como serviço

### Frontend
- **Streamlit 1.31.0** - Framework para dashboards interativos
- **Pandas 2.2.0** - Manipulação de dados

### Outras
- **python-dotenv 1.0.0** - Gerenciamento de variáveis de ambiente
- **requests 2.31.0** - Requisições HTTP

## 📁 Estrutura do Projeto

```
mvp-crm/
│
├── app.py                      # Inicialização do Flask e rotas principais
├── Procfile                    # Configuração de deploy no Render
├── requirements.txt            # Dependências Python
├── runtime.txt                 # Versão do Python (3.11.9)
│
├── routes/
│   ├── webhooks.py            # Endpoint de recebimento de webhooks
│   └── clients.py             # Endpoints de consulta de clientes
│
├── services/
│   ├── database_service.py    # Interface com Supabase
│   ├── scheduler.py           # Lógica de automação agendada (✅ Implementado)
│   └── whatsapp_service.py    # Integração com API de mensagens (✅ Estrutura pronta)
│
├── utils/
│   ├── __init__.py
│   └── validators.py          # Validações de telefone e email (✅ Implementado)
│
└── streamlit_app/
    └── app.py                 # Dashboard Streamlit
```

## 🔧 Instalação

### Pré-requisitos

- Python 3.11.9 (obrigatório)
- Conta no Supabase
- Conta no Render (para API)
- Conta no Streamlit Cloud (para dashboard)

### Passo a Passo

1. **Clone o repositório**
```bash
git clone <seu-repositorio>
cd mvp-crm
```

2. **Crie um ambiente virtual**
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

3. **Instale as dependências**
```bash
pip install -r requirements.txt
```

## ⚙️ Configuração

### 1. Variáveis de Ambiente

Crie um arquivo `.env` na raiz do projeto com as seguintes variáveis:

```env
# Supabase
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave-anon-key

# Flask
FLASK_SECRET_KEY=sua-chave-secreta-aqui
PORT=5000

# Segurança da API
API_SECRET_TOKEN=seu-token-secreto-para-webhook

# WhatsApp API (Opcional - quando tiver a API real)
WHATSAPP_API_URL=https://api.whatsapp.com/v1
WHATSAPP_API_TOKEN=seu-token-da-api
WHATSAPP_PHONE_ID=seu-phone-id
WHATSAPP_MOCK_MODE=true  # true = usa mock, false = usa API real
```

### 2. Configuração do Supabase

1. Acesse seu projeto no Supabase
2. Crie a tabela `clientes` com a seguinte estrutura:

```sql
CREATE TABLE clientes (
    id BIGSERIAL PRIMARY KEY,
    nome VARCHAR(255) NOT NULL,
    telefone VARCHAR(20) NOT NULL,
    email VARCHAR(255),
    status VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 3. Configuração do Streamlit Cloud

No painel do Streamlit Cloud, adicione os seguintes secrets:

```
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_KEY=sua-chave-anon-key
```

## 🚀 Uso

### Executar Localmente

#### API Flask (Backend)
```bash
python app.py
```

A API estará disponível em `http://localhost:5000`

#### Dashboard Streamlit
```bash
streamlit run streamlit_app/app.py
```

O dashboard estará disponível em `http://localhost:8501`

### Enviar Dados via Webhook

Exemplo de requisição POST para `/api/webhook`:

```bash
curl -X POST http://localhost:5000/api/webhook \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer seu-token-secreto" \
  -d '{
    "nome": "João Silva",
    "telefone": "5511987654321",
    "email": "joao@example.com"
  }'
```

**Resposta de Sucesso (201):**
```json
{
  "message": "Cliente recebido com sucesso!",
  "client_id": 1,
  "nome": "João Silva"
}
```

**Validações Implementadas:**
- ✅ Telefone: Valida formato brasileiro (DDD + número)
- ✅ Email: Valida formato e estrutura
- ✅ Nome: Mínimo de 2 caracteres
- ✅ Sanitização automática de dados

## 🌐 Deploy

### API Flask no Render

1. Conecte seu repositório ao Render
2. Configure as variáveis de ambiente no painel do Render
3. O `Procfile` já está configurado: `web: gunicorn app:app`
4. O `runtime.txt` garante Python 3.11.9

**Importante**: Certifique-se de que todas as variáveis do `.env` estejam configuradas no Render.

### Dashboard no Streamlit Cloud

1. Conecte seu repositório ao Streamlit Cloud
2. Configure o caminho do app: `streamlit_app/app.py`
3. Adicione os secrets do Supabase no painel de configurações

## 📡 API Endpoints

### `GET /`
Health check da API.

**Resposta:**
```json
{
  "status": "online",
  "system": "MVP CRM & Automation",
  "version": "1.0.0"
}
```

### `POST /api/webhook`
Recebe dados de novos clientes.

**Headers:**
- `Authorization: Bearer <API_SECRET_TOKEN>`
- `Content-Type: application/json`

**Body:**
```json
{
  "nome": "string (obrigatório)",
  "telefone": "string (obrigatório)",
  "email": "string (opcional)"
}
```

### `GET /api/clients`
Lista todos os clientes (para debug/integrações).

### `GET /api/clients/<id>`
Retorna um cliente específico pelo ID.

## 🔒 Segurança

- ✅ Autenticação via token no webhook
- ✅ Validação de campos obrigatórios
- ✅ Validação de formato de telefone (regex)
- ✅ Validação de formato de email
- ✅ Sanitização de dados (telefone e email)
- ✅ Uso de variáveis de ambiente para credenciais
- ✅ Proteção contra SQL Injection (via Supabase client)
- ✅ Logging estruturado para auditoria

## 📊 Dashboard

O painel Streamlit exibe:

- **Métricas Principais**:
  - Total de Clientes
  - Novos Clientes
  - Status do Sistema

- **Tabela de Clientes**: Visualização completa da base de dados
- **Atualização em Tempo Real**: Botão para refresh dos dados

## 🤖 Automação (Scheduler)

O sistema possui um scheduler que executa automaticamente:

- **Tarefa Diária**: Executa todos os dias às 09:00
- **Função**: Envia mensagens de acompanhamento para clientes novos
- **Status**: Verificável via endpoint `/` (health check)

**Nota**: No Render, o scheduler funciona apenas se o worker estiver sempre ativo. Para produção, considere usar um worker separado ou cron jobs do Render.

### Como funciona:

1. O scheduler busca todos os clientes do banco
2. Filtra clientes que ainda não receberam acompanhamento
3. Envia mensagem via WhatsApp (mock ou real, conforme configuração)
4. Atualiza o status do cliente no banco de dados
5. Registra logs de todas as operações

## 🔮 Melhorias Futuras

### Curto Prazo
- [x] ✅ Validação de formato de telefone (regex)
- [x] ✅ Validação de email
- [x] ✅ Implementação completa do scheduler (automação diária)
- [x] ✅ Logs estruturados
- [x] ✅ Tratamento de erros mais robusto
- [ ] Integração real com API de WhatsApp (estrutura pronta, aguardando credenciais)
- [ ] Testes automatizados

### Médio Prazo
- [ ] Autenticação de usuários no dashboard
- [ ] Filtros e busca na tabela de clientes
- [ ] Gráficos e visualizações (Streamlit charts)
- [ ] Exportação de dados (CSV/Excel)
- [ ] Paginação na API
- [ ] Rate limiting

### Longo Prazo
- [ ] Sistema de tags/categorias para clientes
- [ ] Histórico de interações
- [ ] Integração com múltiplos canais (Email, SMS, WhatsApp)
- [ ] Dashboard de analytics avançado
- [ ] API REST completa (CRUD)
- [ ] Testes automatizados

## 🐛 Troubleshooting

### Erro: "Variáveis do Supabase não configuradas"
- Verifique se o arquivo `.env` existe e contém `SUPABASE_URL` e `SUPABASE_KEY`

### Erro: "Token inválido" no webhook
- Confirme que o header `Authorization` está sendo enviado corretamente
- Verifique se o token no `.env` corresponde ao enviado na requisição

### Erro no Deploy: "Python version incompatible"
- Certifique-se de que `runtime.txt` contém `python-3.11.9`
- No Render, verifique se a versão do Python está correta

## 📝 Licença

Este projeto é um MVP desenvolvido para demonstração de conceitos.

## 👤 Autor

Desenvolvido como MVP para automação de vendas.

---

**Status do Deploy:**
- ✅ Dashboard Streamlit: **Online** (Streamlit Cloud)
- 🔄 API Flask: **Em Deploy** (Render.com)

---

*Última atualização: Novembro 2025*

