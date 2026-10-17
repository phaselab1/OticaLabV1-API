# Ótica Lab API

API multi-tenant para clínicas/óticas com múltiplas empresas e unidades — construída com FastAPI, arquitetura feature-first, e Supabase self-hosted (PostgREST) como camada de persistência.

```
company (empresa)
  └── company_unit (unidade/filial)
        ├── appointment (agendamento — empresa/unidade próprias, cliente opcional)
        └── customer (cliente, só passa a existir a partir de um agendamento completed)
```

Documentação completa: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Quickstart

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
cp .env.example .env   # preencha SUPABASE_URL, SUPABASE_KEY, SECRET_KEY
```

Aplique a migration ([db/migrations/0001_initial_schema.sql](db/migrations/0001_initial_schema.sql)) no SQL Editor do seu Supabase, crie o primeiro usuário (`super_admin`) manualmente — veja [db/migrations/README.md](db/migrations/README.md) — e suba a API:

```bash
.venv/bin/uvicorn app.main:app --reload
```

- Swagger/OpenAPI interativo: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`
- Health check: `http://localhost:8000/health`

## Testes e qualidade

```bash
.venv/bin/pytest              # 61 testes
.venv/bin/ruff check .        # lint
.venv/bin/ruff format --check .
.venv/bin/mypy app            # type-check estrito
```

O `pre-commit` já roda os três automaticamente em todo commit (`pre-commit install` uma vez, depois é automático).

## Postman

Collection completa (49 requests, todos os endpoints + casos de erro 400/401/403/404/409/422), com autenticação e encadeamento de IDs automáticos:

- [docs/postman/OticaLabV1-API.postman_collection.json](docs/postman/OticaLabV1-API.postman_collection.json)
- [docs/postman/OticaLabV1-API.local.postman_environment.json](docs/postman/OticaLabV1-API.local.postman_environment.json)

Importe os dois no Postman, selecione o ambiente "Ótica Lab - Local", preencha `login_email`/`login_password` com um `super_admin` existente, e rode a coleção pasta por pasta (a ordem já resolve as dependências entre empresa → unidade → cliente → agendamento).

## Docker

```bash
docker build -t oticalab-api .
docker run -p 8000:8000 --env-file .env -e WEB_CONCURRENCY=4 oticalab-api
```

## Estrutura do projeto

```
app/
├── main.py              # composição da aplicação
├── core/                 # config, database, security, exceptions globais
├── shared/                # utilitários genéricos (paginação, etc.)
├── auth/                  # login (JWT)
├── users/                 # usuários do sistema + roles
├── companies/              # empresas, unidades, vínculos de acesso
├── customers/               # clientes
└── appointments/             # agendamentos + histórico de auditoria
```

Cada feature segue `model.py` / `schema.py` / `repository.py` / `service.py` / `router.py` / `exceptions.py` / `dependencies.py`.
