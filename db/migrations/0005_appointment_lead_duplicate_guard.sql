-- A 0004 tornou appointments.customer_id nullable pra suportar leads.
-- Efeito colateral não intencional: uq_appointments_customer_scheduled_at
-- é (customer_id, scheduled_at), e o Postgres trata NULL como sempre
-- distinto num índice único — então dois (ou mais) agendamentos pro MESMO
-- lead (mesmo nome + nascimento, mesma empresa) no MESMO horário exato
-- deixaram de ser bloqueados enquanto customer_id continuar nulo (antes
-- da promoção a cliente). Este índice parcial restaura essa proteção
-- especificamente para o caso de lead, espelhando a regra que já vale
-- pra cliente promovido.
CREATE UNIQUE INDEX uq_appointments_lead_scheduled_at
ON appointments (company_id, lead_full_name, lead_date_of_birth, scheduled_at)
WHERE customer_id IS NULL AND deleted_at IS NULL;
