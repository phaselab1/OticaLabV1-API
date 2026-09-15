# Migrations

Sem Alembic (a API usa o SDK do Supabase, não SQLAlchemy). Cada arquivo aqui é aplicado manualmente, em ordem, direto no Postgres do Supabase self-hosted — via SQL Editor do Supabase Studio ou `psql`.

Numeração sequencial (`0001_`, `0002_`, ...), sem edição de arquivos já aplicados em produção; mudanças posteriores viram uma nova migration.
