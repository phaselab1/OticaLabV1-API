-- Correções de segurança encontradas em auditoria (StrangeFix):
--
-- A) A API só acessa o Postgres via PostgREST usando a service_role key
--    (que ignora RLS por padrão) — nunca via anon/authenticated. O
--    Supabase self-hosted, por padrão, concede a anon/authenticated
--    privilégios completos em toda tabela nova do schema public. Como
--    este projeto nunca usa essas roles, qualquer vazamento futuro da
--    chave anon (ex: hardcoded num front-end) daria acesso irrestrito
--    de leitura/escrita a TODAS as tabelas. Fecha isso habilitando RLS
--    (sem nenhuma policy — nega tudo por padrão) e revogando os GRANTs
--    padrão dessas duas roles em todas as tabelas da aplicação.
--
-- B) Quatro funções de trigger liam o estado "ativo" (deleted_at) do
--    registro-pai (companies/company_units/customers) sem travar a
--    linha lida. Numa corrida real: uma transação desativa a empresa
--    (UPDATE deleted_at) enquanto outra, concorrente, está criando uma
--    unidade/cliente/agendamento sob essa mesma empresa — sem lock, as
--    duas podem commitar e o banco fica com uma unidade/cliente/
--    agendamento "vivo" pendurado numa empresa desativada. Corrigido
--    trocando o SELECT solto por SELECT ... FOR SHARE, que trava a
--    linha-pai contra qualquer UPDATE concorrente até esta transação
--    terminar.
--
-- C) Nenhuma function fixava search_path, deixando a resolução de
--    nomes (companies, users, etc.) sujeita ao search_path da sessão
--    que a invoca — não explorável hoje (nenhuma é SECURITY DEFINER e
--    nenhum role não-confiável tem CREATE no schema public), mas é
--    hardening padrão de defesa em profundidade. Todas as functions
--    passam a fixar SET search_path = public.

-- === A) RLS + revogação de privilégios padrão de anon/authenticated ===

ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_units ENABLE ROW LEVEL SECURITY;
ALTER TABLE company_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointments ENABLE ROW LEVEL SECURITY;
ALTER TABLE appointment_history ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON
    users, companies, company_units, company_users,
    customers, appointments, appointment_history
FROM anon, authenticated;

-- === B) FOR SHARE nas 4 functions que liam estado do pai sem lock ===

CREATE OR REPLACE FUNCTION enforce_company_unit_parent_active()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_deleted_at TIMESTAMPTZ;
BEGIN
    SELECT deleted_at INTO v_deleted_at
    FROM companies WHERE id = NEW.company_id
    FOR SHARE;

    IF v_deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'company % is deactivated', NEW.company_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_company_users_parents_valid()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_company_deleted_at TIMESTAMPTZ;
    v_unit_company_id UUID;
    v_unit_deleted_at TIMESTAMPTZ;
BEGIN
    SELECT deleted_at INTO v_company_deleted_at
    FROM companies WHERE id = NEW.company_id
    FOR SHARE;

    IF v_company_deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'company % is deactivated', NEW.company_id;
    END IF;

    IF NEW.unit_id IS NOT NULL THEN
        SELECT company_id, deleted_at INTO v_unit_company_id, v_unit_deleted_at
        FROM company_units WHERE id = NEW.unit_id
        FOR SHARE;

        IF v_unit_company_id IS DISTINCT FROM NEW.company_id THEN
            RAISE EXCEPTION 'unit % does not belong to company %', NEW.unit_id, NEW.company_id;
        END IF;

        IF v_unit_deleted_at IS NOT NULL THEN
            RAISE EXCEPTION 'unit % is deactivated', NEW.unit_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_customer_parents_valid()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_company_deleted_at TIMESTAMPTZ;
    v_unit_company_id UUID;
    v_unit_deleted_at TIMESTAMPTZ;
BEGIN
    SELECT deleted_at INTO v_company_deleted_at
    FROM companies WHERE id = NEW.company_id
    FOR SHARE;

    IF v_company_deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'company % is deactivated', NEW.company_id;
    END IF;

    SELECT company_id, deleted_at INTO v_unit_company_id, v_unit_deleted_at
    FROM company_units WHERE id = NEW.company_unit_id
    FOR SHARE;

    IF v_unit_company_id IS DISTINCT FROM NEW.company_id THEN
        RAISE EXCEPTION 'unit % does not belong to company %', NEW.company_unit_id, NEW.company_id;
    END IF;

    IF v_unit_deleted_at IS NOT NULL THEN
        RAISE EXCEPTION 'unit % is deactivated', NEW.company_unit_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION enforce_appointment_company_access()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_company_id UUID;
    v_unit_id UUID;
    v_customer_deleted_at TIMESTAMPTZ;
BEGIN
    SELECT company_id, company_unit_id, deleted_at
    INTO v_company_id, v_unit_id, v_customer_deleted_at
    FROM customers WHERE id = NEW.customer_id
    FOR SHARE;

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
$$;

-- === C) search_path pinning nas demais functions (sem lock a adicionar) ===

CREATE OR REPLACE FUNCTION enforce_company_users_manager_requires_unit()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_role user_role;
BEGIN
    SELECT role INTO v_role FROM users WHERE id = NEW.user_id;

    IF v_role = 'manager' AND NEW.unit_id IS NULL THEN
        RAISE EXCEPTION 'manager % must be linked to a specific unit, not the whole company', NEW.user_id;
    END IF;

    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION user_has_unit_access(p_user_id UUID, p_company_id UUID, p_unit_id UUID)
RETURNS BOOLEAN
LANGUAGE plpgsql
SET search_path = public
AS $$
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
$$;

CREATE OR REPLACE FUNCTION enforce_customer_company_access()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
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
$$;

CREATE OR REPLACE FUNCTION block_appointment_history_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    RAISE EXCEPTION 'appointment_history is append-only: % is not allowed', TG_OP;
END;
$$;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$;

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
SET search_path = public
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

-- === Rate limiting de login (Postgres-backed, para escalar horizontalmente
-- sem estado em memória do processo) ===

CREATE TABLE login_attempts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL,
    success BOOLEAN NOT NULL,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_login_attempts_email_attempted_at ON login_attempts (email, attempted_at);

ALTER TABLE login_attempts ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON login_attempts FROM anon, authenticated;
