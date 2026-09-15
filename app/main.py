from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.appointments.exceptions import register_appointment_exception_handlers
from app.appointments.router import router as appointments_router
from app.auth.exceptions import register_auth_exception_handlers
from app.auth.router import router as auth_router
from app.companies.exceptions import register_company_exception_handlers
from app.companies.router import router as companies_router
from app.core.config import APP_NAME, get_settings
from app.core.database import close_supabase
from app.core.exceptions import register_exception_handlers
from app.customers.exceptions import register_customer_exception_handlers
from app.customers.router import router as customers_router
from app.users.exceptions import register_user_exception_handlers
from app.users.router import router as users_router

settings = get_settings()

API_DESCRIPTION = """
API do Ótica Lab — sistema multi-tenant para clínicas/óticas com múltiplas empresas e unidades.

## Autenticação

Toda rota protegida exige um `Bearer` token JWT no header `Authorization`.
Obtenha um token em `POST /auth/login` com e-mail e senha. Não há
auto-registro: o primeiro usuário (`super_admin`) é criado manualmente
direto no banco (veja `db/migrations/README.md`).

## Hierarquia e papéis (roles)

```
company (empresa)
  └── company_unit (unidade/filial)
        └── customer (cliente, cadastrado numa unidade especifica)
              └── appointment (agendamento, herda empresa/unidade do cliente)
```

O acesso de um usuário a uma empresa/unidade vem de `company_users`
(vínculo de acesso), exceto para `super_admin`, que tem acesso irrestrito
sem precisar de vínculo.

- **`super_admin`** — acesso global. Deve informar `company_id` e
  `company_unit_id` explicitamente ao cadastrar um cliente.
- **`admin`** — acesso a toda a empresa vinculada (todas as unidades).
  `company_id` automático; `company_unit_id` ainda precisa ser escolhido.
- **`manager`** — acesso a uma unidade específica, nunca à empresa
  inteira. Ambos automáticos (só tem acesso a uma unidade).
- **`attendant`** — empresa inteira ou unidade(s) específica(s).
  Automático se vinculado a exatamente uma unidade; senão precisa escolher.

## Soft delete

Toda entidade (exceto `appointment_history`) usa soft delete via
`deleted_at` — nenhum `DELETE` é físico. Um registro soft-deletado
some das listagens e passa a responder `404` em endpoints de detalhe.

## Auditoria de agendamentos

Toda edição de um agendamento (`PUT /appointments/{id}`) grava
automaticamente uma linha em `appointment_history` (imutável, somente
leitura via `GET /appointments/{id}/history`), na mesma transação da
atualização — não é uma chamada separada da aplicação.
""".strip()

OPENAPI_TAGS = [
    {
        "name": "auth",
        "description": "Autenticação. Único jeito de obter um token JWT — não há auto-registro.",
    },
    {
        "name": "users",
        "description": (
            "Usuários do sistema (quem opera, não quem é atendido). "
            "Criar/editar/excluir exige role `super_admin`."
        ),
    },
    {
        "name": "companies",
        "description": (
            "Empresas, suas unidades, e os vínculos de acesso (`company_users`) que "
            "concedem a um usuário acesso a uma empresa inteira ou a uma unidade específica."
        ),
    },
    {
        "name": "customers",
        "description": "Clientes atendidos (pacientes), cadastrados numa empresa/unidade.",
    },
    {
        "name": "appointments",
        "description": (
            "Agendamentos, escopados à empresa/unidade do cliente. Toda edição gera uma "
            "linha imutável de auditoria em `appointment_history`."
        ),
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await close_supabase()


app = FastAPI(
    title=APP_NAME,
    description=API_DESCRIPTION,
    version="1.0.0",
    debug=settings.debug,
    lifespan=lifespan,
    openapi_tags=OPENAPI_TAGS,
    contact={"name": "Ótica Lab", "email": "dev@oticalab.com"},
)

register_exception_handlers(app)
register_company_exception_handlers(app)
register_customer_exception_handlers(app)
register_appointment_exception_handlers(app)
register_user_exception_handlers(app)
register_auth_exception_handlers(app)

app.include_router(auth_router)
app.include_router(users_router)
app.include_router(companies_router)
app.include_router(customers_router)
app.include_router(appointments_router)


@app.get("/health", tags=["health"], summary="Health check")
async def health_check() -> dict[str, str]:
    """Endpoint de liveness — usado por load balancers/orquestradores. Não requer autenticação."""
    return {"status": "ok"}
