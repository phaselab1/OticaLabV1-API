-- Agendamento deixa de exigir um `customer_id` na criação. Quem marca o
-- horário começa como LEAD: nome, data de nascimento e telefone ficam
-- guardados direto no agendamento (lead_full_name/lead_date_of_birth/
-- lead_phone), sem nenhuma linha em `customers`. Só quando o agendamento
-- é marcado como `completed` (compareceu) é que o lead de fato vira
-- cliente — nesse momento a aplicação cria (ou reaproveita, se já existir
-- pelo nome+nascimento na empresa) a linha em `customers` e liga
-- `customer_id`. Um `no_show`/`cancelled` nunca gera cliente.
--
-- Como o agendamento agora pode existir sem cliente, empresa/unidade
-- (antes só disponíveis via join em customer_id) passam a viver
-- diretamente em appointments.

ALTER TABLE appointments
    ALTER COLUMN customer_id DROP NOT NULL,
    ADD COLUMN company_id UUID REFERENCES companies (id),
    ADD COLUMN company_unit_id UUID REFERENCES company_units (id),
    ADD COLUMN lead_full_name VARCHAR(255),
    ADD COLUMN lead_date_of_birth DATE,
    ADD COLUMN lead_phone VARCHAR(20);

-- O backfill abaixo é um UPDATE administrativo (dado histórico, não uma
-- ação de usuário) em TODA linha de appointments — inclusive linhas cujo
-- customer_id aponta pra cliente já soft-deletado, ou cujo
-- updated_by_user_id registra um usuário que hoje não tem mais vínculo de
-- acesso àquela empresa/unidade (histórico legítimo de edições antigas).
-- Os triggers de validação da 0001 (que ainda são os ativos neste ponto —
-- a versão nova só é criada mais abaixo) rejeitariam esse UPDATE por
-- qualquer um desses motivos. Desabilita o trigger só para o backfill,
-- escopo mínimo possível, e reabilita logo em seguida.
ALTER TABLE appointments DISABLE TRIGGER trg_appointments_enforce_company_access;

-- Backfill: todo agendamento já existente tem customer_id preenchido —
-- copia os dados do cliente vinculado antes de tornar as colunas novas
-- obrigatórias.
UPDATE appointments a
SET
    company_id = c.company_id,
    company_unit_id = c.company_unit_id,
    lead_full_name = c.full_name,
    lead_date_of_birth = c.date_of_birth,
    lead_phone = c.phone
FROM customers c
WHERE a.customer_id = c.id;

ALTER TABLE appointments ENABLE TRIGGER trg_appointments_enforce_company_access;

ALTER TABLE appointments
    ALTER COLUMN company_id SET NOT NULL,
    ALTER COLUMN company_unit_id SET NOT NULL,
    ALTER COLUMN lead_full_name SET NOT NULL,
    ALTER COLUMN lead_date_of_birth SET NOT NULL,
    ADD CONSTRAINT chk_appointments_lead_phone_format
        CHECK (lead_phone IS NULL OR lead_phone ~ '^[0-9]{10,11}$');

CREATE INDEX idx_appointments_company_id ON appointments (company_id);
CREATE INDEX idx_appointments_company_unit_id ON appointments (company_unit_id);

-- company_unit_id precisa pertencer a company_id, empresa/unidade
-- referenciadas precisam estar ativas, e — se já promovido a cliente —
-- o customer_id precisa pertencer à mesma empresa do agendamento e não
-- estar soft-deletado. Mesmo padrão de enforce_customer_parents_valid,
-- com FOR SHARE para travar a linha-pai contra desativação concorrente.
CREATE OR REPLACE FUNCTION enforce_appointment_parents_valid()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_company_deleted_at TIMESTAMPTZ;
    v_unit_company_id UUID;
    v_unit_deleted_at TIMESTAMPTZ;
    v_customer_company_id UUID;
    v_customer_deleted_at TIMESTAMPTZ;
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

    IF NEW.customer_id IS NOT NULL THEN
        SELECT company_id, deleted_at INTO v_customer_company_id, v_customer_deleted_at
        FROM customers WHERE id = NEW.customer_id
        FOR SHARE;

        IF v_customer_company_id IS DISTINCT FROM NEW.company_id THEN
            RAISE EXCEPTION 'customer % does not belong to company %', NEW.customer_id, NEW.company_id;
        END IF;

        IF v_customer_deleted_at IS NOT NULL THEN
            RAISE EXCEPTION 'customer % is deactivated', NEW.customer_id;
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

CREATE TRIGGER trg_appointments_parents_valid
BEFORE INSERT OR UPDATE ON appointments
FOR EACH ROW
EXECUTE FUNCTION enforce_appointment_parents_valid();

-- Reescreve a checagem de autorização: antes derivava empresa/unidade do
-- customer_id (join obrigatório); agora usa as colunas próprias do
-- agendamento, que existem desde a criação independente de cliente.
CREATE OR REPLACE FUNCTION enforce_appointment_company_access()
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

-- Amplia a function de atualização atômica para também poder setar
-- customer_id — usada quando a aplicação promove o lead a cliente ao
-- marcar `completed`, na MESMA transação do UPDATE + histórico.
-- p_customer_id omitido/NULL mantém o customer_id atual (COALESCE).
CREATE OR REPLACE FUNCTION update_appointment_with_history(
    p_appointment_id UUID,
    p_changed_by_user_id UUID,
    p_new_scheduled_at TIMESTAMPTZ DEFAULT NULL,
    p_new_status appointment_status DEFAULT NULL,
    p_new_notes TEXT DEFAULT NULL,
    p_notes_provided BOOLEAN DEFAULT FALSE,
    p_customer_id UUID DEFAULT NULL
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
        customer_id = COALESCE(p_customer_id, customer_id),
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
