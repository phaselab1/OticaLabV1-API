-- CORREÇÃO DE EMERGÊNCIA: a migration 0002 revogou privilégios de
-- `anon, authenticated` esperando isolar só essas duas roles (o padrão do
-- Supabase hospedado, onde service_role tem GRANTs próprios e independentes).
--
-- Nesta instância self-hosted, porém, `service_role` herda privilégios por
-- MEMBRESIA em `authenticated`/`anon` (não tem GRANTs diretos próprios) —
-- então o REVOKE da 0002 cascateou e cortou o acesso da própria API,
-- derrubando toda leitura/escrita via service_role.
--
-- Esta migration restaura explicitamente os privilégios de service_role em
-- cada tabela, independente de qualquer relação de herança de role, e
-- garante BYPASSRLS nela — sem isso, o RLS habilitado na 0002 (sem nenhuma
-- policy) bloquearia a própria service_role também, já que BYPASSRLS é o
-- único jeito de uma role continuar enxergando linhas com RLS ligado e zero
-- policies.

GRANT ALL PRIVILEGES ON
    users, companies, company_units, company_users,
    customers, appointments, appointment_history, login_attempts
TO service_role;

ALTER ROLE service_role BYPASSRLS;
