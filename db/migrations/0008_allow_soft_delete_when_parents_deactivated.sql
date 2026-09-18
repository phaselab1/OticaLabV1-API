-- Migration 0008: Permitir soft-delete de agendamentos cujo cliente/empresa/unidade já foram desativados
--
-- Problema:
-- A trigger `enforce_appointment_parents_valid` barrava qualquer UPDATE em `appointments`
-- se a empresa, unidade ou cliente estivessem com `deleted_at IS NOT NULL`
-- (ex: `RAISE EXCEPTION 'customer % is deactivated', NEW.customer_id;`).
-- Quando um cliente era soft-deletado e o usuário tentava soft-deletar o agendamento associado
-- (executando `UPDATE appointments SET deleted_at = ...`), a trigger disparava e impedia a exclusão!
--
-- Solução:
-- Se o agendamento já está sendo desativado (`NEW.deleted_at IS NOT NULL`), não devemos barrar
-- o arquivamento/exclusão lógica mesmo que os pais (empresa, unidade ou cliente) já tenham sido desativados.

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
    -- Se o agendamento está sendo deletado (soft-delete), permite a operação sem validar pais ativos
    IF NEW.deleted_at IS NOT NULL THEN
        RETURN NEW;
    END IF;

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

-- Aplica a mesma regra de desativação para clientes (customers)
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
    -- Se o cliente está sendo deletado (soft-delete), permite a operação sem validar pais ativos
    IF NEW.deleted_at IS NOT NULL THEN
        RETURN NEW;
    END IF;

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

