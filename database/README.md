# 📊 Scripts de Banco de Dados - MVP CRM

## Como usar

1. Acesse o **Supabase Dashboard**
2. Vá em **SQL Editor**
3. Cole o conteúdo completo do arquivo `schema.sql`
4. Execute o script
5. ✅ **Pronto!** O script é idempotente (pode rodar múltiplas vezes sem erro)

## O que o script faz

### 1. Atualiza tabela `clientes`
Adiciona os campos necessários para o MVP:
- `data_primeira_compra` - Data da primeira compra (usado para calcular próximas ações)
- `procedimento` - Tipo de procedimento realizado
- `valor_pago` - Valor pago pelo cliente (validação: >= 0)
- `proxima_acao` - Data/hora da próxima ação programada
- `ultima_acao` - Data/hora da última ação realizada
- `observacoes` - Observações sobre o cliente

**Validações:**
- `data_primeira_compra` não pode ser no futuro
- `valor_pago` deve ser >= 0
- `proxima_acao` deve ser >= `created_at`

### 2. Cria tabela `acoes`
Armazena todas as ações realizadas (mensagens e ligações):
- `id` - ID único
- `id_cliente` - Referência ao cliente (CASCADE)
- `tipo` - 'mensagem' (automática) ou 'ligacao' (manual)
- `conteudo` - Conteúdo da mensagem ou notas da ligação
- `data` - Data/hora da ação (não pode ser no futuro)
- `resultado` - 'sim', 'nao', 'sem_resposta', 'agendou', 'comprou', 'pendente'
- `created_at` / `updated_at` - Timestamps automáticos

**Validações:**
- `tipo` deve ser 'mensagem' ou 'ligacao'
- `resultado` deve ser um dos valores permitidos
- `data` não pode ser mais de 1 hora no futuro
- Não permite reverter ações de clientes que compraram ou agendaram

### 3. Cria tabela `auditoria`
Sistema completo de logs e auditoria:
- Registra todas as operações (INSERT, UPDATE, DELETE)
- Armazena dados antigos e novos em JSONB
- Rastreia usuário, data/hora, IP e user-agent
- Permite auditoria completa do sistema

### 4. Cria índices otimizados
Melhora a performance das consultas:
- Índices em campos de busca frequente
- Índices compostos para consultas complexas
- Índices parciais (WHERE) para melhor performance

### 5. Cria triggers automáticos
- **update_updated_at**: Atualiza `updated_at` automaticamente
- **registrar_auditoria**: Registra todas as alterações na tabela auditoria
- **validar_atualizacao_acao**: Valida regras de negócio antes de atualizar ações
- **atualizar_ultima_acao_cliente**: Atualiza `ultima_acao` do cliente automaticamente

### 6. Cria views úteis
- **vw_acoes_pendentes**: Lista ações pendentes com dados do cliente (para interface de tarefas)
- **vw_estatisticas_acoes**: Estatísticas agregadas (para dashboard)
- **vw_clientes_proxima_acao**: Clientes que precisam de ação (para filtros)

## Verificação

Após executar, verifique se tudo foi criado corretamente:

```sql
-- Ver estrutura da tabela clientes
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'clientes'
ORDER BY ordinal_position;

-- Ver estrutura da tabela acoes
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'acoes'
ORDER BY ordinal_position;

-- Ver estrutura da tabela auditoria
SELECT column_name, data_type, is_nullable
FROM information_schema.columns 
WHERE table_name = 'auditoria'
ORDER BY ordinal_position;

-- Verificar views criadas
SELECT table_name, view_definition
FROM information_schema.views
WHERE table_schema = 'public'
AND table_name LIKE 'vw_%';

-- Verificar triggers criados
SELECT trigger_name, event_manipulation, event_object_table
FROM information_schema.triggers
WHERE trigger_schema = 'public';
```

## Testes Rápidos

```sql
-- Testar view de ações pendentes
SELECT * FROM vw_acoes_pendentes LIMIT 5;

-- Testar view de estatísticas
SELECT * FROM vw_estatisticas_acoes;

-- Testar view de clientes com próxima ação
SELECT * FROM vw_clientes_proxima_acao 
WHERE precisa_acao_hoje = true 
LIMIT 5;

-- Ver últimas operações de auditoria
SELECT 
    tabela_afetada,
    operacao,
    id_registro,
    usuario,
    data_operacao
FROM auditoria
ORDER BY data_operacao DESC
LIMIT 10;
```

## Características do Script

✅ **Idempotente**: Pode ser executado múltiplas vezes sem erro  
✅ **Seguro**: Validações em múltiplas camadas  
✅ **Auditável**: Registra todas as alterações  
✅ **Performático**: Índices otimizados  
✅ **Documentado**: Comentários em todas as estruturas  
✅ **Compatível**: PostgreSQL/Supabase

