-- Telefone é compartilhado por famílias: identidade = telefone + similaridade de nome.
BEGIN;
CREATE EXTENSION IF NOT EXISTS unaccent WITH SCHEMA extensions;
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA extensions;

ALTER TABLE customers DROP CONSTRAINT uq_customers_company_id_full_name;

DROP INDEX IF EXISTS idx_customers_phone;
CREATE INDEX idx_customers_company_phone ON customers (company_id, phone) WHERE deleted_at IS NULL;

ALTER TABLE customers
    ADD COLUMN needs_review BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN review_reason TEXT;

CREATE OR REPLACE FUNCTION match_customers_by_phone(
    p_company_id UUID,
    p_phones TEXT[],
    p_full_name TEXT
)
RETURNS TABLE (id UUID, score REAL)
LANGUAGE sql
STABLE
SET search_path = public, extensions
AS $$
    SELECT c.id,
           similarity(lower(unaccent(trim(c.full_name))), lower(unaccent(trim(p_full_name)))) AS score
    FROM customers c
    WHERE c.company_id = p_company_id
      AND c.phone = ANY (p_phones)
      AND c.deleted_at IS NULL
    ORDER BY score DESC, c.created_at ASC;
$$;

REVOKE ALL ON FUNCTION match_customers_by_phone(UUID, TEXT[], TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION match_customers_by_phone(UUID, TEXT[], TEXT) TO service_role;

COMMIT;
