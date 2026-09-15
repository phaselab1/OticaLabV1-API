-- Extensão necessária para geração de UUID via gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Todas as tabelas usam UUID como chave primária (em vez de BIGSERIAL/
-- inteiro autoincremento). Isso é padrão de mercado global: não expõe
-- volume de registros pela sequência do ID, não colide entre ambientes/
-- réplicas diferentes, e não depende de coordenação central para gerar
-- um novo ID.

-- Papel do usuário no sistema. É GLOBAL: o mesmo role vale em todas as
-- empresas às quais o usuário tem acesso (não varia por empresa).
-- super_admin: cria empresas, unidades e usuários; acesso irrestrito a
--              tudo, sem precisar de vínculo explícito em company_users.
--              Ao cadastrar um cliente, precisa informar empresa E unidade.
-- admin:       acesso a toda a empresa (todas as unidades dela). Ao
--              cadastrar um cliente, a empresa é automática (vínculo),
--              mas ainda precisa escolher a unidade.
-- manager:     gerencia uma unidade específica (nunca a empresa inteira —
--              ver trg_company_users_manager_requires_unit). Vê tudo da(s)
--              unidade(s) à(s) qual(is) está vinculado.
-- attendant:   pode estar vinculado à empresa inteira ou apenas a
--              unidade(s) específica(s). Se vinculado a uma única unidade,
--              ela é preenchida automaticamente ao cadastrar um cliente.
CREATE TYPE user_role AS ENUM (
    'super_admin',
    'admin',
    'manager',
    'attendant'
);

-- Situação atual de um agendamento. ENUM em vez de VARCHAR + CHECK, pelo
-- mesmo motivo do user_role: o próprio tipo já rejeita qualquer valor fora
-- da lista no nível do banco, sem depender de constraint solta.
CREATE TYPE appointment_status AS ENUM (
    'scheduled',
    'confirmed',
    'cancelled',
    'completed',
    'no_show'
);

-- Usuários do sistema (quem opera, não quem é atendido).
-- O vínculo com empresa/unidade NÃO fica aqui: vive em company_users,
-- pois um usuário pode acessar várias empresas e unidades ao mesmo tempo.
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

CREATE INDEX idx_users_role ON users (role);
CREATE INDEX idx_users_deleted_at ON users (deleted_at);

-- Empresas (ex: "Clínica Nova Visão") cadastradas pelo super_admin.
-- Uma empresa pode ter uma ou várias unidades (ver company_units).
-- created_by_user_id rastreia qual super_admin criou a empresa.
-- cnpj validado por formato (14 dígitos numéricos); não valida dígito
-- verificador (regra de negócio do CNPJ em si), só a forma do dado.
-- Soft-delete via deleted_at.
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    cnpj VARCHAR(14) NOT NULL,
    state CHAR(2) NOT NULL,
    city VARCHAR(255) NOT NULL,
    created_by_user_id UUID NOT NULL REFERENCES users (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_companies_cnpj UNIQUE (cnpj),
    CONSTRAINT chk_companies_cnpj_format CHECK (cnpj ~ '^[0-9]{14}$'),
    CONSTRAINT chk_companies_state_valid CHECK (state IN (
        'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG',
        'PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'
    ))
);

CREATE INDEX idx_companies_created_by_user_id ON companies (created_by_user_id);
CREATE INDEX idx_companies_deleted_at ON companies (deleted_at);

-- Unidades (filiais/localidades) de uma empresa. Ex: Nova Visão hoje só
-- tem a unidade ARG, mas pode crescer para PMW, CAU, CGR, AME, BHZ etc.
-- "code" é o identificador curto usado no dia a dia (ex: "BHZ").
-- Cada unidade tem CNPJ próprio (padrão matriz/filial brasileiro: mesma
-- raiz, sufixo diferente), independente do CNPJ da empresa-mãe. Assim como
-- em companies, o cnpj aqui só valida formato (14 dígitos numéricos), não
-- o dígito verificador.
-- Soft-delete via deleted_at.
CREATE TABLE company_units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies (id),
    name VARCHAR(255) NOT NULL,
    code VARCHAR(10) NOT NULL,
    cnpj VARCHAR(14) NOT NULL,
    state CHAR(2) NOT NULL,
    city VARCHAR(255) NOT NULL,
    created_by_user_id UUID NOT NULL REFERENCES users (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_company_units_company_id_code UNIQUE (company_id, code),
    CONSTRAINT uq_company_units_cnpj UNIQUE (cnpj),
    CONSTRAINT chk_company_units_cnpj_format CHECK (cnpj ~ '^[0-9]{14}$'),
    CONSTRAINT chk_company_units_state_valid CHECK (state IN (
        'AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG',
        'PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO'
    ))
);

CREATE INDEX idx_company_units_company_id ON company_units (company_id);
CREATE INDEX idx_company_units_created_by_user_id ON company_units (created_by_user_id);
CREATE INDEX idx_company_units_deleted_at ON company_units (deleted_at);

-- Garante que a empresa referenciada por uma nova unidade está ativa
-- (não faz sentido criar uma unidade sob uma empresa já desativada).
CREATE OR REPLACE FUNCTION enforce_company_unit_parent_active()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM companies WHERE id = NEW.company_id AND deleted_at IS NOT NULL) THEN
        RAISE EXCEPTION 'company % is deactivated', NEW.company_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_company_units_parent_active
BEFORE INSERT OR UPDATE ON company_units
FOR EACH ROW
EXECUTE FUNCTION enforce_company_unit_parent_active();

-- Vínculo de acesso entre usuário e empresa, com granularidade opcional
-- de unidade:
--   unit_id IS NULL     -> acesso a TODAS as unidades da empresa (caso do admin)
--   unit_id IS NOT NULL -> acesso apenas àquela unidade específica (caso do
--                          atendente vinculado só a uma ou algumas unidades)
-- super_admin não precisa de linha aqui, seu acesso é global pelo role.
-- granted_by_user_id rastreia quem concedeu esse acesso (o super_admin ou
-- admin responsável pela vinculação).
-- Revogar acesso é soft-delete desta linha, não da empresa/unidade/usuário.
CREATE TABLE company_users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies (id),
    user_id UUID NOT NULL REFERENCES users (id),
    unit_id UUID REFERENCES company_units (id),
    granted_by_user_id UUID NOT NULL REFERENCES users (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_company_users_company_id ON company_users (company_id);
CREATE INDEX idx_company_users_user_id ON company_users (user_id);
CREATE INDEX idx_company_users_unit_id ON company_users (unit_id);
CREATE INDEX idx_company_users_granted_by_user_id ON company_users (granted_by_user_id);
CREATE INDEX idx_company_users_deleted_at ON company_users (deleted_at);

-- Evita dois vínculos ativos redundantes: um usuário só pode ter UM vínculo
-- de "empresa inteira" (unit_id nulo) ativo por empresa...
CREATE UNIQUE INDEX uq_company_users_whole_company
ON company_users (company_id, user_id)
WHERE unit_id IS NULL AND deleted_at IS NULL;

-- ...e só UM vínculo ativo por unidade específica.
CREATE UNIQUE INDEX uq_company_users_specific_unit
ON company_users (company_id, user_id, unit_id)
WHERE unit_id IS NOT NULL AND deleted_at IS NULL;

-- Garante que, se unit_id for informado, ela realmente pertença à
-- company_id do mesmo vínculo (evita amarrar usuário a unidade de outra
-- empresa por engano), e que empresa/unidade referenciadas estão ativas
-- (não é permitido conceder vínculo novo a empresa/unidade desativada).
CREATE OR REPLACE FUNCTION enforce_company_users_parents_valid()
RETURNS TRIGGER AS $$
DECLARE
    v_unit_company_id UUID;
    v_unit_deleted_at TIMESTAMPTZ;
BEGIN
    IF EXISTS (SELECT 1 FROM companies WHERE id = NEW.company_id AND deleted_at IS NOT NULL) THEN
        RAISE EXCEPTION 'company % is deactivated', NEW.company_id;
    END IF;

    IF NEW.unit_id IS NOT NULL THEN
        SELECT company_id, deleted_at INTO v_unit_company_id, v_unit_deleted_at
        FROM company_units WHERE id = NEW.unit_id;

        IF v_unit_company_id IS DISTINCT FROM NEW.company_id THEN
            RAISE EXCEPTION 'unit % does not belong to company %', NEW.unit_id, NEW.company_id;
        END IF;

        IF v_unit_deleted_at IS NOT NULL THEN
            RAISE EXCEPTION 'unit % is deactivated', NEW.unit_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_company_users_parents_valid
BEFORE INSERT OR UPDATE ON company_users
FOR EACH ROW
EXECUTE FUNCTION enforce_company_users_parents_valid();

-- Regra específica do role manager: diferente de admin (empresa inteira)
-- e attendant (pode ser empresa inteira ou unidade específica), o manager
-- é sempre vinculado a uma unidade específica — nunca à empresa inteira.
-- Um vínculo com unit_id nulo para um usuário manager é rejeitado aqui.
CREATE OR REPLACE FUNCTION enforce_company_users_manager_requires_unit()
RETURNS TRIGGER AS $$
DECLARE
    v_role user_role;
BEGIN
    SELECT role INTO v_role FROM users WHERE id = NEW.user_id;

    IF v_role = 'manager' AND NEW.unit_id IS NULL THEN
        RAISE EXCEPTION 'manager % must be linked to a specific unit, not the whole company', NEW.user_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_company_users_manager_requires_unit
BEFORE INSERT OR UPDATE ON company_users
FOR EACH ROW
EXECUTE FUNCTION enforce_company_users_manager_requires_unit();

-- Função central de autorização: um usuário tem acesso a uma unidade se
-- for super_admin (acesso global), ou se tiver vínculo ativo em
-- company_users para aquela empresa com unit_id nulo (empresa inteira)
-- ou unit_id igual à unidade em questão (unidade específica).
--
-- Um usuário soft-deletado (users.deleted_at preenchido) NUNCA passa nesta
-- checagem, mesmo que o vínculo em company_users ainda esteja ativo — sem
-- isso, desativar um usuário não revogaria de fato o acesso dele.
CREATE OR REPLACE FUNCTION user_has_unit_access(p_user_id UUID, p_company_id UUID, p_unit_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
    v_role user_role;
BEGIN
    SELECT role INTO v_role FROM users WHERE id = p_user_id AND deleted_at IS NULL;

    IF v_role IS NULL THEN
        RETURN FALSE;
    END IF;

    IF v_role = 'super_admin' THEN
        RETURN TRUE;
    END IF;

    RETURN EXISTS (
        SELECT 1 FROM company_users
        WHERE user_id = p_user_id
          AND company_id = p_company_id
          AND deleted_at IS NULL
          AND (unit_id IS NULL OR unit_id = p_unit_id)
    );
END;
$$ LANGUAGE plpgsql;

-- Clientes atendidos (pacientes da clínica/ótica).
-- company_id identifica a empresa (usado na deduplicação abaixo, pois o
-- mesmo cliente pode ser atendido em unidades diferentes da mesma empresa
-- e continuar sendo um único cadastro). company_unit_id identifica a
-- unidade onde o cliente foi cadastrado — e é também a unidade de TODOS
-- os agendamentos desse cliente (decisão de negócio: agendamento sempre
-- ocorre na unidade de cadastro do cliente, sem transferência entre unidades).
-- full_name + date_of_birth foi escolhido como identidade do cliente em vez
-- de CPF: CPF resolveria a unicidade com mais rigor, mas foi descartado de
-- propósito por carregar tratamento de dado sensível (LGPD) e a necessidade
-- de validar dígito verificador — custo que não compensava para este estágio.
-- phone é apenas indexado (não único) e validado só por formato (10 ou 11
-- dígitos, DDD incluso, sem máscara): não vira identidade do cliente porque
-- pode ser compartilhado de forma legítima (ex: telefone da mãe usado para
-- agendar os filhos).
-- Rastreia quem cadastrou e quem fez a última alteração.
-- Soft-delete via deleted_at.
CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies (id),
    company_unit_id UUID NOT NULL REFERENCES company_units (id),
    full_name VARCHAR(255) NOT NULL,
    date_of_birth DATE NOT NULL,
    phone VARCHAR(20),
    -- Usuário que cadastrou o cliente originalmente. Nunca muda depois de criado.
    created_by_user_id UUID NOT NULL REFERENCES users (id),
    -- Usuário responsável pela última alteração. Nulo até a primeira edição.
    updated_by_user_id UUID REFERENCES users (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    -- full_name + date_of_birth como identidade prática do cliente,
    -- escopada por EMPRESA (não por unidade): o mesmo cliente atendido em
    -- unidades diferentes da mesma empresa é uma única pessoa, um único
    -- cadastro. Empresas diferentes podem ter cada uma um cliente com o
    -- mesmo nome e data de nascimento sem conflito.
    CONSTRAINT uq_customers_company_id_full_name_date_of_birth UNIQUE (company_id, full_name, date_of_birth),
    CONSTRAINT chk_customers_phone_format CHECK (phone IS NULL OR phone ~ '^[0-9]{10,11}$')
);

CREATE INDEX idx_customers_company_id ON customers (company_id);
CREATE INDEX idx_customers_company_unit_id ON customers (company_unit_id);
CREATE INDEX idx_customers_created_by_user_id ON customers (created_by_user_id);
CREATE INDEX idx_customers_updated_by_user_id ON customers (updated_by_user_id);
CREATE INDEX idx_customers_phone ON customers (phone);
CREATE INDEX idx_customers_deleted_at ON customers (deleted_at);

-- Garante que company_unit_id realmente pertença a company_id, e que
-- empresa e unidade referenciadas estão ativas (não é permitido cadastrar
-- cliente novo em empresa/unidade desativada).
CREATE OR REPLACE FUNCTION enforce_customer_parents_valid()
RETURNS TRIGGER AS $$
DECLARE
    v_unit_company_id UUID;
    v_unit_deleted_at TIMESTAMPTZ;
BEGIN
    IF EXISTS (SELECT 1 FROM companies WHERE id = NEW.company_id AND deleted_at IS NOT NULL) THEN
        RAISE EXCEPTION 'company % is deactivated', NEW.company_id;
    END IF;

    SELECT company_id, deleted_at INTO v_unit_company_id, v_unit_deleted_at
    FROM company_units WHERE id = NEW.company_unit_id;

    IF v_unit_company_id IS DISTINCT FROM NEW.company_id THEN
        RAISE EXCEPTION 'unit % does not belong to company %', NEW.company_unit_id, NEW.company_id;
    END IF;

    IF v_unit_deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'unit % is deactivated', NEW.company_unit_id;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_customers_parents_valid
BEFORE INSERT OR UPDATE ON customers
FOR EACH ROW
EXECUTE FUNCTION enforce_customer_parents_valid();

-- Garante, no nível do banco, que só quem tem acesso à unidade do cliente
-- (super_admin, vínculo de empresa inteira, ou vínculo daquela unidade
-- específica) pode criar ou alterar esse cliente. Fecha a lacuna de um
-- usuário multi-empresa/multi-unidade conseguir gravar dados fora do
-- escopo ao qual está autorizado.
CREATE OR REPLACE FUNCTION enforce_customer_company_access()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        IF NOT user_has_unit_access(NEW.created_by_user_id, NEW.company_id, NEW.company_unit_id) THEN
            RAISE EXCEPTION 'user % has no access to unit % of company %', NEW.created_by_user_id, NEW.company_unit_id, NEW.company_id;
        END IF;
    ELSIF TG_OP = 'UPDATE' AND NEW.updated_by_user_id IS NOT NULL THEN
        IF NOT user_has_unit_access(NEW.updated_by_user_id, NEW.company_id, NEW.company_unit_id) THEN
            RAISE EXCEPTION 'user % has no access to unit % of company %', NEW.updated_by_user_id, NEW.company_unit_id, NEW.company_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_customers_enforce_company_access
BEFORE INSERT OR UPDATE ON customers
FOR EACH ROW
EXECUTE FUNCTION enforce_customer_company_access();

-- Agendamentos. Entidade central do sistema.
-- Não guarda company_id/company_unit_id diretamente: a empresa e a unidade
-- do agendamento são as mesmas do customer_id (evita duplicar o dado e
-- criar inconsistência), refletindo a decisão de que o agendamento sempre
-- ocorre na unidade de cadastro do cliente.
-- Soft-delete via deleted_at: cancelamento de verdade usa status = 'cancelled',
-- deleted_at é reservado para remoção administrativa (erro de cadastro, duplicata).
-- Decisão de negócio: múltiplos agendamentos de CLIENTES DIFERENTES no mesmo
-- horário são permitidos (ex: mais de um atendimento simultâneo na mesma
-- unidade). O que NÃO é permitido é o MESMO cliente ter dois agendamentos
-- ativos no mesmo scheduled_at (ver uq_appointments_customer_scheduled_at) —
-- isso é tratado como duplicata de cadastro, não como agendamento legítimo.
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

-- Bloqueia o MESMO cliente de ter dois agendamentos ativos no mesmo
-- scheduled_at exato. Parcial (WHERE deleted_at IS NULL) para que um
-- agendamento removido administrativamente não trave um reagendamento
-- legítimo no mesmo horário depois.
CREATE UNIQUE INDEX uq_appointments_customer_scheduled_at
ON appointments (customer_id, scheduled_at)
WHERE deleted_at IS NULL;

-- Garante que o cliente referenciado está ativo (não é permitido criar
-- agendamento novo para um cliente já soft-deletado), e que só quem tem
-- acesso à unidade do cliente pode criar/alterar o agendamento. Como
-- appointments não guarda company_id/company_unit_id direto, busca ambos
-- através do customer_id.
CREATE OR REPLACE FUNCTION enforce_appointment_company_access()
RETURNS TRIGGER AS $$
DECLARE
    v_company_id UUID;
    v_unit_id UUID;
    v_customer_deleted_at TIMESTAMPTZ;
BEGIN
    SELECT company_id, company_unit_id, deleted_at
    INTO v_company_id, v_unit_id, v_customer_deleted_at
    FROM customers WHERE id = NEW.customer_id;

    IF v_customer_deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'customer % is deactivated', NEW.customer_id;
    END IF;

    IF TG_OP = 'INSERT' THEN
        IF NOT user_has_unit_access(NEW.created_by_user_id, v_company_id, v_unit_id) THEN
            RAISE EXCEPTION 'user % has no access to unit % of company %', NEW.created_by_user_id, v_unit_id, v_company_id;
        END IF;
    ELSIF TG_OP = 'UPDATE' AND NEW.updated_by_user_id IS NOT NULL THEN
        IF NOT user_has_unit_access(NEW.updated_by_user_id, v_company_id, v_unit_id) THEN
            RAISE EXCEPTION 'user % has no access to unit % of company %', NEW.updated_by_user_id, v_unit_id, v_company_id;
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_appointments_enforce_company_access
BEFORE INSERT OR UPDATE ON appointments
FOR EACH ROW
EXECUTE FUNCTION enforce_appointment_company_access();

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

CREATE TRIGGER trg_companies_updated_at
BEFORE UPDATE ON companies
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_company_units_updated_at
BEFORE UPDATE ON company_units
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_company_users_updated_at
BEFORE UPDATE ON company_users
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
