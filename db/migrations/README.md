# Migrations

Sem Alembic (a API usa o SDK do Supabase, não SQLAlchemy). Cada arquivo aqui é aplicado manualmente, em ordem, direto no Postgres do Supabase self-hosted — via SQL Editor do Supabase Studio ou `psql`.

Numeração sequencial (`0001_`, `0002_`, ...), sem edição de arquivos já aplicados em produção; mudanças posteriores viram uma nova migration.

## Primeiro usuário (bootstrap)

Não existe endpoint de auto-registro — todo `POST /users` exige um `super_admin` autenticado. Por isso o primeiro `super_admin` precisa ser inserido manualmente, direto no banco:

```sql
INSERT INTO users (full_name, email, password_hash, role)
VALUES ('Admin', 'admin@example.com', '<hash bcrypt>', 'super_admin');
```

Um `super_admin` tem acesso irrestrito a tudo (sem precisar de vínculo em `company_users`) e é o único role que pode criar empresas, unidades e outros usuários.

O hash bcrypt pode ser gerado localmente com `python -c "from app.core.security import hash_password; print(hash_password('sua-senha'))"` (dentro do venv do projeto).
