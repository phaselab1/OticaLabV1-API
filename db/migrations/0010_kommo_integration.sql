-- Integração Kommo: config por empresa, outbox de eventos e vínculo de leads/contatos.

CREATE TABLE kommo_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies (id),
    company_unit_id UUID NOT NULL REFERENCES company_units (id),
    -- Autor dos registros; precisa de acesso à unidade (triggers de customers/appointments).
    service_user_id UUID NOT NULL REFERENCES users (id),
    subdomain VARCHAR(100) NOT NULL,
    access_token_encrypted TEXT NOT NULL,
    tenant_token_hash CHAR(64) NOT NULL,
    pipeline_id BIGINT NOT NULL,
    scheduled_status_id BIGINT NOT NULL,
    date_field_id BIGINT NOT NULL,
    time_field_id BIGINT NOT NULL,
    referral_field_id BIGINT,
    phone_field_id BIGINT NOT NULL,
    timezone VARCHAR(64) NOT NULL DEFAULT 'America/Araguaina',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT chk_kommo_integrations_subdomain CHECK (subdomain ~ '^[a-z0-9-]+$')
);

CREATE UNIQUE INDEX uq_kommo_integrations_company
ON kommo_integrations (company_id) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_kommo_integrations_tenant_token_hash
ON kommo_integrations (tenant_token_hash);

CREATE TYPE kommo_event_status AS ENUM ('pending', 'processing', 'done', 'failed');

CREATE TABLE kommo_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_id UUID NOT NULL REFERENCES kommo_integrations (id),
    company_id UUID NOT NULL REFERENCES companies (id),
    kommo_lead_id BIGINT NOT NULL,
    payload JSONB NOT NULL,
    status kommo_event_status NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_until TIMESTAMPTZ,
    last_error TEXT,
    appointment_id UUID REFERENCES appointments (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX idx_kommo_events_claimable
ON kommo_events (next_attempt_at) WHERE status IN ('pending', 'processing');
CREATE INDEX idx_kommo_events_lead ON kommo_events (company_id, kommo_lead_id);

-- needs_review/review_reason de customers já vêm da 0009.
ALTER TABLE customers ADD COLUMN kommo_contact_id BIGINT;

CREATE UNIQUE INDEX uq_customers_company_kommo_contact
ON customers (company_id, kommo_contact_id)
WHERE kommo_contact_id IS NOT NULL AND deleted_at IS NULL;

ALTER TABLE appointments
    ADD COLUMN kommo_lead_id BIGINT,
    ADD COLUMN needs_review BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN review_reason TEXT,
    ADD COLUMN scheduled_time_unknown BOOLEAN NOT NULL DEFAULT FALSE;

CREATE UNIQUE INDEX uq_appointments_company_kommo_lead_scheduled
ON appointments (company_id, kommo_lead_id)
WHERE kommo_lead_id IS NOT NULL AND status = 'scheduled' AND deleted_at IS NULL;

-- Agendamentos do Kommo não podem ser barrados por conflito de horário (atendimento por ordem de chegada).
DROP INDEX uq_appointments_customer_scheduled_at;
CREATE UNIQUE INDEX uq_appointments_customer_scheduled_at
ON appointments (customer_id, scheduled_at)
WHERE deleted_at IS NULL AND kommo_lead_id IS NULL;

DROP INDEX uq_appointments_lead_scheduled_at;
CREATE UNIQUE INDEX uq_appointments_lead_scheduled_at
ON appointments (company_id, lead_full_name, scheduled_at)
WHERE customer_id IS NULL AND deleted_at IS NULL AND kommo_lead_id IS NULL;

-- Evento 'processing' com lease vencido volta a ser reivindicável (réplica morreu no meio).
CREATE OR REPLACE FUNCTION claim_kommo_events(p_limit INT, p_lease_seconds INT)
RETURNS SETOF kommo_events
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    UPDATE kommo_events e
    SET status = 'processing',
        attempts = e.attempts + 1,
        locked_until = now() + make_interval(secs => p_lease_seconds)
    WHERE e.id IN (
        SELECT id FROM kommo_events
        WHERE next_attempt_at <= now()
          AND (status = 'pending' OR (status = 'processing' AND locked_until < now()))
        ORDER BY next_attempt_at
        LIMIT p_limit
        FOR UPDATE SKIP LOCKED
    )
    RETURNING e.*;
END;
$$;

CREATE OR REPLACE FUNCTION upsert_kommo_appointment(
    p_company_id UUID,
    p_company_unit_id UUID,
    p_user_id UUID,
    p_kommo_lead_id BIGINT,
    p_customer_id UUID,
    p_lead_full_name VARCHAR,
    p_lead_phone VARCHAR,
    p_scheduled_at TIMESTAMPTZ,
    p_scheduled_time_unknown BOOLEAN,
    p_notes TEXT,
    p_needs_review BOOLEAN,
    p_review_reason TEXT
)
RETURNS SETOF appointments
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_old appointments;
    v_new appointments;
BEGIN
    SELECT * INTO v_old FROM appointments
    WHERE company_id = p_company_id
      AND kommo_lead_id = p_kommo_lead_id
      AND status = 'scheduled'
      AND deleted_at IS NULL
    FOR UPDATE;

    IF NOT FOUND THEN
        INSERT INTO appointments (
            company_id, company_unit_id, customer_id, lead_full_name, lead_phone,
            created_by_user_id, scheduled_at, status, notes,
            kommo_lead_id, needs_review, review_reason, scheduled_time_unknown
        ) VALUES (
            p_company_id, p_company_unit_id, p_customer_id, p_lead_full_name, p_lead_phone,
            p_user_id, p_scheduled_at, 'scheduled', p_notes,
            p_kommo_lead_id, p_needs_review, p_review_reason, p_scheduled_time_unknown
        )
        ON CONFLICT (company_id, kommo_lead_id)
            WHERE kommo_lead_id IS NOT NULL AND status = 'scheduled' AND deleted_at IS NULL
        DO NOTHING
        RETURNING * INTO v_new;

        IF v_new.id IS NOT NULL THEN
            RETURN NEXT v_new;
            RETURN;
        END IF;

        -- Corrida: outra transação inseriu entre o SELECT e o INSERT; atualiza a linha dela.
        SELECT * INTO v_old FROM appointments
        WHERE company_id = p_company_id AND kommo_lead_id = p_kommo_lead_id
          AND status = 'scheduled' AND deleted_at IS NULL
        FOR UPDATE;
    END IF;

    UPDATE appointments SET
        customer_id = COALESCE(p_customer_id, customer_id),
        lead_full_name = p_lead_full_name,
        lead_phone = p_lead_phone,
        scheduled_at = p_scheduled_at,
        scheduled_time_unknown = p_scheduled_time_unknown,
        notes = p_notes,
        needs_review = p_needs_review,
        review_reason = p_review_reason,
        updated_by_user_id = p_user_id
    WHERE id = v_old.id
    RETURNING * INTO v_new;

    INSERT INTO appointment_history (
        appointment_id, changed_by_user_id,
        previous_scheduled_at, new_scheduled_at,
        previous_status, new_status,
        previous_notes, new_notes
    ) VALUES (
        v_new.id, p_user_id,
        v_old.scheduled_at, v_new.scheduled_at,
        v_old.status, v_new.status,
        v_old.notes, v_new.notes
    );

    RETURN NEXT v_new;
END;
$$;

ALTER TABLE kommo_integrations ENABLE ROW LEVEL SECURITY;
ALTER TABLE kommo_events ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON kommo_integrations, kommo_events FROM anon, authenticated;
GRANT ALL PRIVILEGES ON kommo_integrations, kommo_events TO service_role;

REVOKE ALL ON FUNCTION claim_kommo_events(INT, INT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION claim_kommo_events(INT, INT) TO service_role;

REVOKE ALL ON FUNCTION upsert_kommo_appointment(
    UUID, UUID, UUID, BIGINT, UUID, VARCHAR, VARCHAR, TIMESTAMPTZ, BOOLEAN, TEXT, BOOLEAN, TEXT
) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION upsert_kommo_appointment(
    UUID, UUID, UUID, BIGINT, UUID, VARCHAR, VARCHAR, TIMESTAMPTZ, BOOLEAN, TEXT, BOOLEAN, TEXT
) TO service_role;
