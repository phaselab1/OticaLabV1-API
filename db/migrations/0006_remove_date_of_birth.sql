-- Data de nascimento deixa de ser rastreada — nem no cadastro de cliente,
-- nem no lead de agendamento. A identidade prática do cliente passa a ser
-- só o nome completo (telefone continua guardado, mas nunca foi único).
--
-- DESTRUTIVO: qualquer data de nascimento já gravada é perdida
-- permanentemente ao rodar esta migration — não há como recuperar depois.

-- === customers ===

ALTER TABLE customers DROP CONSTRAINT uq_customers_company_id_full_name_date_of_birth;
ALTER TABLE customers DROP COLUMN date_of_birth;

-- Sem data de nascimento, nome completo (por empresa) passa a ser a
-- identidade única do cliente. Dois clientes reais com o mesmo nome exato
-- na mesma empresa agora colidem — risco aceito explicitamente ao remover
-- a data de nascimento como campo de desambiguação.
ALTER TABLE customers ADD CONSTRAINT uq_customers_company_id_full_name UNIQUE (company_id, full_name);

-- === appointments (lead) ===

DROP INDEX uq_appointments_lead_scheduled_at;
ALTER TABLE appointments DROP COLUMN lead_date_of_birth;

-- Mesmo raciocínio: sem data de nascimento, a duplicidade de lead no mesmo
-- horário passa a ser detectada só por nome completo.
CREATE UNIQUE INDEX uq_appointments_lead_scheduled_at
ON appointments (company_id, lead_full_name, scheduled_at)
WHERE customer_id IS NULL AND deleted_at IS NULL;
