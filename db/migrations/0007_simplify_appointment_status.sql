-- Simplifica os status de agendamento: remove `confirmed` (não trazia
-- distinção de negócio suficiente sobre `scheduled`) e renomeia `completed`
-- para `attended` (nome em inglês que já significa "compareceu", sem
-- depender de doc externa pra entender o que o status faz).
--
-- Novo enum: scheduled, attended, cancelled, no_show.

-- 1) Qualquer agendamento hoje em `confirmed` volta para `scheduled` antes
-- do valor deixar de existir — é o estado não-terminal mais próximo. Isso é
-- um UPDATE administrativo (dado histórico, não uma ação de usuário) em
-- TODA linha nesse status — inclusive as de empresas/unidades já
-- desativadas, ou cujo updated_by_user_id registra um usuário que hoje não
-- tem mais vínculo de acesso. As triggers de validação da appointments
-- rejeitariam esse UPDATE por qualquer um desses motivos, e a de
-- appointment_history bloqueia QUALQUER UPDATE por padrão (é append-only).
-- Desabilita as três só para o backfill, escopo mínimo possível.
ALTER TABLE appointments DISABLE TRIGGER trg_appointments_parents_valid;
ALTER TABLE appointments DISABLE TRIGGER trg_appointments_enforce_company_access;
ALTER TABLE appointment_history DISABLE TRIGGER trg_appointment_history_immutable;

UPDATE appointments SET status = 'scheduled' WHERE status = 'confirmed';
UPDATE appointment_history SET previous_status = 'scheduled' WHERE previous_status = 'confirmed';
UPDATE appointment_history SET new_status = 'scheduled' WHERE new_status = 'confirmed';

ALTER TABLE appointments ENABLE TRIGGER trg_appointments_parents_valid;
ALTER TABLE appointments ENABLE TRIGGER trg_appointments_enforce_company_access;
ALTER TABLE appointment_history ENABLE TRIGGER trg_appointment_history_immutable;

-- 2) Renomeia completed -> attended no enum atual (suportado nativamente
-- pelo Postgres, preserva o mesmo OID de tipo — não afeta a function que
-- ainda referencia esse tipo neste ponto).
ALTER TYPE appointment_status RENAME VALUE 'completed' TO 'attended';

-- 3) A function referencia o tipo do enum no parâmetro p_new_status —
-- precisa ser removida antes de trocarmos o tipo por um novo objeto
-- (mesmo nome, mas sem 'confirmed'), senão o DROP TYPE do passo 4 falha
-- por dependência. Existem DUAS sobrecargas hoje: a atual (7 parâmetros,
-- com p_customer_id, criada na 0004) e uma órfã de 6 parâmetros da 0001 —
-- CREATE OR REPLACE FUNCTION não substitui uma function ao adicionar um
-- parâmetro novo no fim, mesmo com DEFAULT; ele cria uma sobrecarga
-- separada e deixa a antiga intacta, sem uso mas ainda dependendo do tipo.
DROP FUNCTION update_appointment_with_history(
    UUID, UUID, TIMESTAMPTZ, appointment_status, TEXT, BOOLEAN, UUID
);
DROP FUNCTION IF EXISTS update_appointment_with_history(
    UUID, UUID, TIMESTAMPTZ, appointment_status, TEXT, BOOLEAN
);

-- 4) Recria o enum sem 'confirmed' (Postgres não suporta remover valor de
-- enum diretamente — o caminho padrão é recriar o tipo).
ALTER TYPE appointment_status RENAME TO appointment_status_old;
CREATE TYPE appointment_status AS ENUM ('scheduled', 'attended', 'cancelled', 'no_show');

ALTER TABLE appointments ALTER COLUMN status DROP DEFAULT;
ALTER TABLE appointments
    ALTER COLUMN status TYPE appointment_status USING status::text::appointment_status;
ALTER TABLE appointments ALTER COLUMN status SET DEFAULT 'scheduled'::appointment_status;

ALTER TABLE appointment_history
    ALTER COLUMN previous_status TYPE appointment_status USING previous_status::text::appointment_status;
ALTER TABLE appointment_history
    ALTER COLUMN new_status TYPE appointment_status USING new_status::text::appointment_status;

DROP TYPE appointment_status_old;

-- 5) Recria a function apontando pro novo tipo (mesmo corpo da 0004).
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
