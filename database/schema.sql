-- ============================================
-- SCHEMA DO BANCO DE DADOS - MVP CRM
-- ============================================
-- Execute este SQL no Supabase SQL Editor
-- Script idempotente (pode ser executado múltiplas vezes)
-- Baseado na especificação técnica completa do MVP
-- ============================================

-- ============================================
-- 1. ATUALIZAR TABELA CLIENTES
-- ============================================

DO $$ 
BEGIN 
    -- Adicionar colunas à tabela clientes (idempotente)
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'clientes') THEN
        ALTER TABLE clientes 
        ADD COLUMN IF NOT EXISTS data_primeira_compra DATE,
        ADD COLUMN IF NOT EXISTS procedimento VARCHAR(255),
        ADD COLUMN IF NOT EXISTS valor_pago NUMERIC(10,2) CHECK (valor_pago >= 0),
        ADD COLUMN IF NOT EXISTS proxima_acao TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS ultima_acao TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS observacoes TEXT,
        ADD COLUMN IF NOT EXISTS cpf VARCHAR(11);
    ELSE
        RAISE NOTICE 'Tabela clientes não existe — pulei adição de colunas.';
    END IF;
EXCEPTION 
    WHEN undefined_table THEN
        RAISE NOTICE 'Tabela clientes não existe — pulei adição de colunas.';
END $$;

-- 1.b Validar existência de created_at em clientes antes de criar constraints
DO $$ 
BEGIN 
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'clientes' AND column_name = 'created_at'
    ) THEN
        -- chk_data_primeira_compra
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint c 
            JOIN pg_class t ON c.conrelid = t.oid 
            WHERE c.conname = 'chk_data_primeira_compra' AND t.relname = 'clientes'
        ) THEN
            ALTER TABLE clientes 
            ADD CONSTRAINT chk_data_primeira_compra 
            CHECK (data_primeira_compra IS NULL OR data_primeira_compra <= CURRENT_DATE);
        END IF;

        -- chk_proxima_acao (usa created_at)
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint c 
            JOIN pg_class t ON c.conrelid = t.oid 
            WHERE c.conname = 'chk_proxima_acao' AND t.relname = 'clientes'
        ) THEN
            ALTER TABLE clientes 
            ADD CONSTRAINT chk_proxima_acao 
            CHECK (proxima_acao IS NULL OR proxima_acao >= created_at);
        END IF;
    ELSE
        RAISE NOTICE 'Coluna clientes.created_at ausente — não criei chk_proxima_acao que depende dela.';
    END IF;
END $$;

-- ============================================
-- 2. CRIAR TABELA AÇÕES
-- ============================================

CREATE TABLE IF NOT EXISTS acoes (
    id BIGSERIAL PRIMARY KEY,
    id_cliente BIGINT NOT NULL REFERENCES clientes(id) ON DELETE CASCADE ON UPDATE CASCADE,
    tipo VARCHAR(50) NOT NULL CHECK (tipo IN ('mensagem', 'ligacao')),
    conteudo TEXT,
    data TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resultado VARCHAR(50) NOT NULL DEFAULT 'pendente' 
        CHECK (resultado IN ('sim', 'nao', 'sem_resposta', 'agendou', 'comprou', 'pendente')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_data_acao CHECK (data <= NOW() + INTERVAL '1 hour')
);

-- ============================================
-- 3. CRIAR ÍNDICES PARA PERFORMANCE
-- ============================================

CREATE INDEX IF NOT EXISTS idx_acoes_id_cliente ON acoes(id_cliente);
CREATE INDEX IF NOT EXISTS idx_acoes_data ON acoes(data DESC);
CREATE INDEX IF NOT EXISTS idx_acoes_resultado ON acoes(resultado);
CREATE INDEX IF NOT EXISTS idx_acoes_tipo ON acoes(tipo);
CREATE INDEX IF NOT EXISTS idx_acoes_id_cliente_resultado ON acoes(id_cliente, resultado) 
    WHERE resultado = 'pendente';

CREATE INDEX IF NOT EXISTS idx_clientes_proxima_acao ON clientes(proxima_acao) 
    WHERE proxima_acao IS NOT NULL;

-- status pode não existir em clientes — checagem antes
DO $$ 
BEGIN 
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'clientes' AND column_name = 'status'
    ) THEN
        EXECUTE 'CREATE INDEX IF NOT EXISTS idx_clientes_status ON clientes(status);';
    ELSE
        RAISE NOTICE 'Coluna clientes.status não encontrada — pulei índice idx_clientes_status.';
    END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_clientes_data_compra ON clientes(data_primeira_compra) 
    WHERE data_primeira_compra IS NOT NULL;

-- Índice/constraint para CPF (único quando presente)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'clientes' AND column_name = 'cpf') THEN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint c JOIN pg_class t ON c.conrelid = t.oid
            WHERE c.conname = 'uniq_clientes_cpf' AND t.relname = 'clientes'
        ) THEN
            ALTER TABLE clientes ADD CONSTRAINT uniq_clientes_cpf UNIQUE (cpf);
        END IF;
        IF NOT EXISTS (
            SELECT 1 FROM pg_class WHERE relname = 'idx_clientes_cpf'
        ) THEN
            CREATE INDEX idx_clientes_cpf ON clientes(cpf);
        END IF;
    ELSE
        RAISE NOTICE 'Coluna clientes.cpf não encontrada — pulei criação de índice/constraint.';
    END IF;
END $$;

-- ============================================
-- 4. TABELA DE AUDITORIA (LOGS)
-- ============================================

CREATE TABLE IF NOT EXISTS auditoria (
    id_auditoria BIGSERIAL PRIMARY KEY,
    tabela_afetada VARCHAR(100) NOT NULL,
    operacao VARCHAR(10) NOT NULL CHECK (operacao IN ('INSERT', 'UPDATE', 'DELETE')),
    id_registro BIGINT,
    dados_antigos JSONB,
    dados_novos JSONB,
    usuario VARCHAR(200),
    data_operacao TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ip_address VARCHAR(45),
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_auditoria_tabela ON auditoria(tabela_afetada);
CREATE INDEX IF NOT EXISTS idx_auditoria_operacao ON auditoria(operacao);
CREATE INDEX IF NOT EXISTS idx_auditoria_data ON auditoria(data_operacao DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_id_registro ON auditoria(id_registro);

-- ============================================
-- 5. FUNÇÕES AUXILIARES
-- ============================================

-- Função para atualizar updated_at automaticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Função para registrar auditoria (ajustada para suportar tabelas sem id)
CREATE OR REPLACE FUNCTION registrar_auditoria()
RETURNS TRIGGER AS $$
DECLARE
    v_dados_antigos JSONB;
    v_dados_novos JSONB;
    v_id_registro BIGINT;
BEGIN
    BEGIN
        IF TG_OP = 'DELETE' THEN
            v_dados_antigos := to_jsonb(OLD);
            v_id_registro := (OLD::jsonb ->> 'id')::bigint;
            INSERT INTO auditoria (tabela_afetada, operacao, id_registro, dados_antigos, usuario, data_operacao)
            VALUES (TG_TABLE_NAME, 'DELETE', v_id_registro, v_dados_antigos, current_user, NOW());
            RETURN OLD;
        ELSIF TG_OP = 'UPDATE' THEN
            v_dados_antigos := to_jsonb(OLD);
            v_dados_novos := to_jsonb(NEW);
            v_id_registro := (NEW::jsonb ->> 'id')::bigint;
            INSERT INTO auditoria (tabela_afetada, operacao, id_registro, dados_antigos, dados_novos, usuario, data_operacao)
            VALUES (TG_TABLE_NAME, 'UPDATE', v_id_registro, v_dados_antigos, v_dados_novos, current_user, NOW());
            RETURN NEW;
        ELSIF TG_OP = 'INSERT' THEN
            v_dados_novos := to_jsonb(NEW);
            v_id_registro := (NEW::jsonb ->> 'id')::bigint;
            INSERT INTO auditoria (tabela_afetada, operacao, id_registro, dados_novos, usuario, data_operacao)
            VALUES (TG_TABLE_NAME, 'INSERT', v_id_registro, v_dados_novos, current_user, NOW());
            RETURN NEW;
        END IF;
    EXCEPTION WHEN others THEN
        -- Fallback: insere sem id se erro ao acessar NEW.id
        INSERT INTO auditoria (tabela_afetada, operacao, dados_novos, usuario, data_operacao)
        VALUES (TG_TABLE_NAME, TG_OP, COALESCE(v_dados_novos, v_dados_antigos), current_user, NOW());
        IF TG_OP = 'DELETE' THEN
            RETURN OLD;
        ELSE
            RETURN NEW;
        END IF;
    END;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- ============================================
-- 6. TRIGGERS: ATUALIZAR UPDATED_AT
-- ============================================

DO $$ 
BEGIN 
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'acoes') THEN
        -- Remover trigger antigo se existir
        DROP TRIGGER IF EXISTS update_acoes_updated_at ON acoes;
        
        -- Criar novo trigger
        CREATE TRIGGER update_acoes_updated_at
            BEFORE UPDATE ON acoes
            FOR EACH ROW
            EXECUTE FUNCTION update_updated_at_column();
    ELSE
        RAISE NOTICE 'Tabela acoes não existe — pulei criação do trigger update_acoes_updated_at.';
    END IF;
END $$;

-- ============================================
-- 7. TRIGGERS DE AUDITORIA
-- ============================================

DO $$ 
BEGIN 
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'clientes') THEN
        DROP TRIGGER IF EXISTS trg_auditoria_clientes ON clientes;
        CREATE TRIGGER trg_auditoria_clientes
            AFTER INSERT OR UPDATE OR DELETE ON clientes
            FOR EACH ROW
            EXECUTE FUNCTION registrar_auditoria();
    ELSE
        RAISE NOTICE 'Tabela clientes não existe — pulei trigger de auditoria clientes.';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'acoes') THEN
        DROP TRIGGER IF EXISTS trg_auditoria_acoes ON acoes;
        CREATE TRIGGER trg_auditoria_acoes
            AFTER INSERT OR UPDATE OR DELETE ON acoes
            FOR EACH ROW
            EXECUTE FUNCTION registrar_auditoria();
    ELSE
        RAISE NOTICE 'Tabela acoes não existe — pulei trigger de auditoria acoes.';
    END IF;
END $$;

-- ============================================
-- 8. TRIGGER: VALIDAR ATUALIZAÇÃO DE AÇÃO
-- ============================================

CREATE OR REPLACE FUNCTION validar_atualizacao_acao()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        -- Não permite reverter ação de cliente que comprou ou agendou
        IF OLD.resultado IN ('comprou', 'agendou') AND NEW.resultado = 'pendente' THEN
            RAISE EXCEPTION 'Não é possível reverter ação de cliente que comprou ou agendou';
        END IF;

        -- Aviso se comprou não for de ligação
        IF NEW.resultado = 'comprou' AND NEW.tipo IS DISTINCT FROM 'ligacao' THEN
            RAISE WARNING 'Resultado "comprou" geralmente é aplicado a ligações';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ 
BEGIN 
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'acoes') THEN
        DROP TRIGGER IF EXISTS trg_validar_acao_update ON acoes;
        CREATE TRIGGER trg_validar_acao_update
            BEFORE UPDATE ON acoes
            FOR EACH ROW
            WHEN (OLD.resultado IS DISTINCT FROM NEW.resultado)
            EXECUTE FUNCTION validar_atualizacao_acao();
    ELSE
        RAISE NOTICE 'Tabela acoes não existe — pulei trigger validar_atualizacao_acao.';
    END IF;
END $$;

-- ============================================
-- 9. TRIGGER: ATUALIZAR ÚLTIMA AÇÃO DO CLIENTE
-- ============================================

CREATE OR REPLACE FUNCTION atualizar_ultima_acao_cliente()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' OR (
        TG_OP = 'UPDATE' AND 
        NEW.resultado IS DISTINCT FROM OLD.resultado AND 
        NEW.resultado != 'pendente'
    ) THEN
        UPDATE clientes 
        SET ultima_acao = NEW.data
        WHERE id = NEW.id_cliente;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ 
BEGIN 
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'acoes') THEN
        DROP TRIGGER IF EXISTS trg_atualizar_ultima_acao ON acoes;
        CREATE TRIGGER trg_atualizar_ultima_acao
            AFTER INSERT OR UPDATE ON acoes
            FOR EACH ROW
            EXECUTE FUNCTION atualizar_ultima_acao_cliente();
    ELSE
        RAISE NOTICE 'Tabela acoes não existe — pulei trigger atualizar_ultima_acao.';
    END IF;
END $$;

-- ============================================
-- 10. COMENTÁRIOS (DOCUMENTAÇÃO)
-- ============================================

DO $$ 
BEGIN 
    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'clientes') THEN
        COMMENT ON TABLE clientes IS 'Tabela principal de clientes do CRM - Armazena informações de clientes e histórico de compras';
        BEGIN
            COMMENT ON COLUMN clientes.data_primeira_compra IS 'Data da primeira compra do cliente - Usado para calcular próximas ações';
            COMMENT ON COLUMN clientes.proxima_acao IS 'Data/hora da próxima ação programada para este cliente';
            COMMENT ON COLUMN clientes.ultima_acao IS 'Data/hora da última ação realizada com sucesso';
            COMMENT ON COLUMN clientes.valor_pago IS 'Valor pago pelo cliente na primeira compra - Deve ser >= 0';
            COMMENT ON COLUMN clientes.procedimento IS 'Tipo de procedimento realizado pelo cliente';
        EXCEPTION 
            WHEN undefined_column THEN
                RAISE NOTICE 'Alguma coluna clientes.* não existe — pulei comentário específico.';
        END;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'acoes') THEN
        COMMENT ON TABLE acoes IS 'Registro de todas as ações realizadas (mensagens e ligações) com rastreamento completo';
        BEGIN
            COMMENT ON COLUMN acoes.tipo IS 'Tipo de ação: mensagem (automática) ou ligacao (manual)';
            COMMENT ON COLUMN acoes.resultado IS 'Resultado da ação: sim, nao, sem_resposta, agendou, comprou, pendente';
            COMMENT ON COLUMN acoes.data IS 'Data/hora em que a ação foi realizada - Não pode ser no futuro';
            COMMENT ON COLUMN acoes.conteudo IS 'Conteúdo da mensagem enviada ou notas da ligação realizada';
        EXCEPTION 
            WHEN undefined_column THEN
                RAISE NOTICE 'Alguma coluna acoes.* não existe — pulei comentário específico.';
        END;
    END IF;

    IF EXISTS (SELECT 1 FROM pg_class WHERE relname = 'auditoria') THEN
        COMMENT ON TABLE auditoria IS 'Log de auditoria para rastreamento de todas as alterações no sistema';
        BEGIN
            COMMENT ON COLUMN auditoria.tabela_afetada IS 'Nome da tabela que foi modificada';
            COMMENT ON COLUMN auditoria.operacao IS 'Tipo de operação: INSERT, UPDATE ou DELETE';
            COMMENT ON COLUMN auditoria.dados_antigos IS 'Dados anteriores (JSON) - Apenas para UPDATE e DELETE';
            COMMENT ON COLUMN auditoria.dados_novos IS 'Dados novos (JSON) - Apenas para INSERT e UPDATE';
        EXCEPTION 
            WHEN undefined_column THEN
                RAISE NOTICE 'Alguma coluna auditoria.* não existe — pulei comentário específico.';
        END;
    END IF;
END $$;

-- ============================================
-- 11. VIEWS PARA FACILITAR CONSULTAS
-- ============================================

-- View: Ações Pendentes (para interface de tarefas)
CREATE OR REPLACE VIEW vw_acoes_pendentes AS
SELECT 
    a.id,
    a.id_cliente,
    COALESCE(c.nome, '') AS cliente_nome,
    COALESCE(c.telefone, '') AS cliente_telefone,
    a.tipo,
    a.conteudo,
    a.data,
    a.resultado,
    a.created_at,
    CASE 
        WHEN a.tipo = 'ligacao' THEN 'Ligação Pendente'
        WHEN a.tipo = 'mensagem' THEN 'Mensagem Pendente'
        ELSE 'Ação Pendente'
    END AS tipo_descricao
FROM acoes a
LEFT JOIN clientes c ON a.id_cliente = c.id
WHERE a.resultado = 'pendente'
ORDER BY a.data ASC;

COMMENT ON VIEW vw_acoes_pendentes IS 'View para facilitar consulta de ações pendentes com dados do cliente - Usado na interface de tarefas';

-- View: Estatísticas de Ações (para dashboard)
CREATE OR REPLACE VIEW vw_estatisticas_acoes AS
SELECT 
    COUNT(*) FILTER (WHERE resultado = 'pendente') AS total_pendentes,
    COUNT(*) FILTER (WHERE resultado = 'comprou') AS total_comprou,
    COUNT(*) FILTER (WHERE resultado = 'agendou') AS total_agendou,
    COUNT(*) FILTER (WHERE resultado = 'sem_resposta') AS total_sem_resposta,
    COUNT(*) FILTER (WHERE tipo = 'mensagem') AS total_mensagens,
    COUNT(*) FILTER (WHERE tipo = 'ligacao') AS total_ligacoes,
    COUNT(*) AS total_acoes,
    ROUND(
        CASE 
            WHEN COUNT(*) = 0 THEN 0 
            ELSE COUNT(*) FILTER (WHERE resultado = 'comprou') * 100.0 / COUNT(*) 
        END, 
        2
    ) AS taxa_conversao_percentual
FROM acoes;

COMMENT ON VIEW vw_estatisticas_acoes IS 'Estatísticas agregadas de todas as ações do sistema - Usado no dashboard';

-- View: Clientes com Próxima Ação (para filtro "pendente de ligação")
CREATE OR REPLACE VIEW vw_clientes_proxima_acao AS
SELECT 
    c.id,
    c.nome,
    c.telefone,
    c.email,
    c.data_primeira_compra,
    c.procedimento,
    c.valor_pago,
    c.status,
    c.proxima_acao,
    c.ultima_acao,
    c.observacoes,
    CASE 
        WHEN c.proxima_acao IS NOT NULL AND c.proxima_acao <= NOW() THEN true
        ELSE false
    END AS precisa_acao_hoje,
    CASE 
        WHEN EXISTS (
            SELECT 1 FROM acoes a 
            WHERE a.id_cliente = c.id 
            AND a.tipo = 'ligacao' 
            AND a.resultado = 'pendente'
        ) THEN true
        ELSE false
    END AS tem_ligacao_pendente
FROM clientes c;

COMMENT ON VIEW vw_clientes_proxima_acao IS 'View para facilitar filtro de clientes que precisam de ação ou têm ligação pendente';

-- ============================================
-- FIM DO SCRIPT
-- ============================================
-- 
-- Script idempotente - pode ser executado múltiplas vezes sem erro
-- Todas as estruturas, validações, triggers e views foram criadas
-- 
-- MVP CRM - Sistema de Automação de Vendas
-- ============================================
