CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TYPE appointment_status AS ENUM (
    'scheduled',
    'confirmed',
    'cancelled',
    'completed',
    'no_show'
);

CREATE TABLE customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(255) NOT NULL,
    date_of_birth DATE NOT NULL,
    phone VARCHAR(20),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT uq_customers_full_name_date_of_birth UNIQUE (full_name, date_of_birth)
);

CREATE INDEX idx_customers_phone ON customers (phone);
CREATE INDEX idx_customers_deleted_at ON customers (deleted_at);

CREATE TABLE appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    customer_id UUID NOT NULL REFERENCES customers (id),
    scheduled_at TIMESTAMPTZ NOT NULL,
    status appointment_status NOT NULL DEFAULT 'scheduled',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_appointments_customer_id ON appointments (customer_id);
CREATE INDEX idx_appointments_scheduled_at ON appointments (scheduled_at);
CREATE INDEX idx_appointments_status ON appointments (status);
CREATE INDEX idx_appointments_deleted_at ON appointments (deleted_at);

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_customers_updated_at
BEFORE UPDATE ON customers
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_appointments_updated_at
BEFORE UPDATE ON appointments
FOR EACH ROW
EXECUTE FUNCTION set_updated_at();
