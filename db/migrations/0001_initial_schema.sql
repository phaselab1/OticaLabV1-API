-- Extensão necessária para geração de UUID via gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Papel do usuário no sistema. ENUM em vez de número mágico (1, 2, ...)
-- para que o próprio banco garanta valores válidos e legíveis.
CREATE TYPE user_role AS ENUM (
    'master',
    'attendant'
);

-- Situação atual de um agendamento. ENUM pelo mesmo motivo do user_role.
CREATE TYPE appointment_status AS ENUM (
    'scheduled',
    'confirmed',
    'cancelled',
    'completed',
    'no_show'
);

-- Usuários do sistema (quem opera, não quem é atendido).
-- Soft-delete via deleted_at: nenhum DELETE físico, apenas marcação.
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role NOT NULL DEFAULT 'attendant',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    -- Um e-mail só pode pertencer a um usuário ativo por vez.
    CONSTRAINT uq_users_email UNIQUE (email)
);

CREATE INDEX idx_users_deleted_at ON users (deleted_at);

-- Clientes atendidos (pacientes da clínica/ótica).
-- Soft-delete via deleted_at, mesmo padrão de users.
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    date_of_birth DATE NOT NULL,
    phone VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    -- full_name + date_of_birth como identidade prática do cliente.
    -- CPF resolveria isso com mais rigor, mas foi descartado por
    -- carregar tratamento de dado sensível (LGPD) e validação extra.
    -- Telefone não entra na constraint porque pode ser compartilhado
    -- (ex: número da mãe usado para agendar filhos).
    CONSTRAINT uq_customers_full_name_date_of_birth UNIQUE (full_name, date_of_birth)
);

-- Telefone é indexado (busca rápida no atendimento) mas não é único:
-- a unicidade de verdade do cliente é full_name + date_of_birth acima.
CREATE INDEX idx_customers_phone ON customers (phone);
CREATE INDEX idx_customers_deleted_at ON customers (deleted_at);

-- Agendamentos. Entidade central do sistema.
-- Soft-delete via deleted_at: cancelamento de verdade usa status = 'cancelled',
-- deleted_at é reservado para remoção administrativa (erro de cadastro, duplicata).
CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers (id),
    -- Atendente que criou o agendamento originalmente. Nunca muda depois de criado.
    created_by_user_id UUID NOT NULL REFERENCES users (id),
    -- Atendente responsável pela última alteração. Nulo até a primeira edição.
    updated_by_user_id UUID REFERENCES users (id),
    -- Data e hora combinadas em um único campo (padrão mais simples
    -- para ordenação e comparação do que dois campos separados).
    scheduled_at TIMESTAMPTZ NOT NULL,
    status appointment_status NOT NULL DEFAULT 'scheduled',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_appointments_customer_id ON appointments (customer_id);
CREATE INDEX idx_appointments_created_by_user_id ON appointments (created_by_user_id);
CREATE INDEX idx_appointments_updated_by_user_id ON appointments (updated_by_user_id);
CREATE INDEX idx_appointments_scheduled_at ON appointments (scheduled_at);
CREATE INDEX idx_appointments_status ON appointments (status);
CREATE INDEX idx_appointments_deleted_at ON appointments (deleted_at);

-- Linha histórica de alterações de cada agendamento (auditoria).
-- Cada UPDATE relevante em appointments deve gerar uma linha aqui,
-- inserida pela aplicação (camada que já sabe qual usuário está autenticado),
-- na mesma transação do UPDATE.
--
-- Esta tabela é a ÚNICA exceção ao padrão de soft-delete do sistema:
-- não tem deleted_at, não tem updated_at, e é travada por trigger contra
-- UPDATE e DELETE (ver trg_appointment_history_immutable), mesmo para
-- usuários com privilégio de superadmin no banco. Um log de auditoria
-- que pode ser alterado ou ocultado deixa de servir como auditoria confiável.
CREATE TABLE appointment_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    appointment_id UUID NOT NULL REFERENCES appointments (id),
    -- Usuário que realizou esta alteração específica (não o dono do agendamento).
    changed_by_user_id UUID NOT NULL REFERENCES users (id),
    previous_scheduled_at TIMESTAMPTZ,
    new_scheduled_at TIMESTAMPTZ,
    previous_status appointment_status,
    new_status appointment_status,
    previous_notes TEXT,
    new_notes TEXT,
    changed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_appointment_history_appointment_id ON appointment_history (appointment_id);
CREATE INDEX idx_appointment_history_changed_by_user_id ON appointment_history (changed_by_user_id);
CREATE INDEX idx_appointment_history_changed_at ON appointment_history (changed_at);

-- Recusa qualquer UPDATE ou DELETE em appointment_history, sem exceção.
CREATE OR REPLACE FUNCTION block_appointment_history_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'appointment_history is append-only: % is not allowed', TG_OP;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_appointment_history_immutable
BEFORE UPDATE OR DELETE ON appointment_history
FOR EACH ROW
EXECUTE FUNCTION block_appointment_history_mutation();

-- Preenchimento automático de updated_at em qualquer UPDATE,
-- para que a aplicação nunca precise lembrar de setar esse campo manualmente.
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_customers_updated_at
BEFORE UPDATE ON customers
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_appointments_updated_at
BEFORE UPDATE ON appointments
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

-- Atualiza um agendamento e grava a linha de auditoria correspondente em
-- appointment_history dentro de uma única transação de banco. É a única
-- forma correta de cumprir a exigência de atomicidade acima: o SDK do
-- Supabase (PostgREST) faz uma chamada HTTP por operação, sem transação
-- entre duas chamadas da aplicação — então "UPDATE + INSERT no histórico"
-- só pode ser atômico se acontecer dentro de uma function no próprio Postgres.
--
-- p_notes_provided distingue "notes não enviado" (mantém o valor atual)
-- de "notes enviado como null" (limpa o campo) — um COALESCE simples não
-- conseguiria diferenciar os dois casos.
--
-- Levanta erro com ERRCODE 'P0002' se o agendamento não existir ou já
-- estiver soft-deleted, para a aplicação traduzir em 404.
CREATE OR REPLACE FUNCTION update_appointment_with_history(
    p_appointment_id UUID,
    p_changed_by_user_id UUID,
    p_new_scheduled_at TIMESTAMPTZ DEFAULT NULL,
    p_new_status appointment_status DEFAULT NULL,
    p_new_notes TEXT DEFAULT NULL,
    p_notes_provided BOOLEAN DEFAULT FALSE
)
RETURNS SETOF appointments
LANGUAGE plpgsql
AS $$
DECLARE
    v_old appointments;
    v_new appointments;
BEGIN
    SELECT * INTO v_old
    FROM appointments
    WHERE id = p_appointment_id AND deleted_at IS NULL
    FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Appointment % not found', p_appointment_id
            USING ERRCODE = 'P0002';
    END IF;

    UPDATE appointments
    SET
        scheduled_at = COALESCE(p_new_scheduled_at, scheduled_at),
        status = COALESCE(p_new_status, status),
        notes = CASE WHEN p_notes_provided THEN p_new_notes ELSE notes END,
        updated_by_user_id = p_changed_by_user_id
    WHERE id = p_appointment_id
    RETURNING * INTO v_new;

    INSERT INTO appointment_history (
        appointment_id,
        changed_by_user_id,
        previous_scheduled_at, new_scheduled_at,
        previous_status, new_status,
        previous_notes, new_notes
    ) VALUES (
        p_appointment_id,
        p_changed_by_user_id,
        v_old.scheduled_at, v_new.scheduled_at,
        v_old.status, v_new.status,
        v_old.notes, v_new.notes
    );

    RETURN NEXT v_new;
END;
$$;
