# Ótica Lab API (NestJS)

API multi-tenant profissional para clínicas/óticas com múltiplas empresas e unidades — construída nativamente com **NestJS**, **TypeScript**, arquitetura modular, e **Supabase self-hosted (PostgREST)** como camada de persistência.

```
company (empresa)
  └── company_unit (unidade/filial)
        ├── appointment (agendamento — empresa/unidade próprias, cliente opcional)
        └── customer (cliente, só passa a existir a partir de um agendamento attended)
```

Documentação completa da arquitetura: **[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)**.

## Quickstart

```bash
# 1. Instalar dependências
npm install --legacy-peer-deps

# 2. Configurar variáveis de ambiente
cp .env.example .env   # configure SUPABASE_URL, SUPABASE_KEY, SECRET_KEY

# 3. Rodar em desenvolvimento
npm run start:dev
```

- **Swagger/OpenAPI interativo**: `http://localhost:8000/docs`
- **Health check**: `http://localhost:8000/health`

## Compilação e Testes

```bash
# Build de produção (TypeScript -> dist)
npm run build

# Execução da suíte de testes unitários
npm test

# Iniciar em produção
npm run start:prod
```

## Docker

```bash
docker build -t oticalab-api .
docker run -p 8000:8000 --env-file .env oticalab-api
```

## Estrutura do Projeto (NestJS)

```
src/
├── main.ts                    # Bootstrap: NestFactory, Swagger, Pipes, Filters, CORS
├── app.module.ts              # Módulo raiz da aplicação
├── config/
│   └── app.config.ts          # Configuração tipada do ambiente (.env)
├── core/
│   ├── database/              # SupabaseService singleton injetável (PostgREST)
│   └── security/              # SecurityService (bcrypt timing-safe hashing)
├── common/
│   ├── dto/                   # PaginationParamsDto, PageDto
│   ├── enums/                 # UserRole, AppointmentStatus
│   ├── filters/               # AllExceptionsFilter (tratamento padronizado de erros)
│   └── utils/                 # formatTitleCase e utilitários
└── modules/
    ├── health/                # GET /health
    ├── auth/                  # POST /auth/login, GET /auth/me, Guards, Passport JWT
    ├── users/                 # CRUD de usuários + papéis (super_admin, admin, etc.)
    ├── companies/             # Empresas, Unidades, Vínculos (company_users)
    ├── customers/             # Clientes com auto-resolução de escopo
    └── appointments/          # Agendamentos, histórico de auditoria imutável, promoção de lead
```

Cada módulo de domínio segue o padrão oficial NestJS:
- `*.module.ts`: declaração e injeção de dependências;
- `*.controller.ts`: endpoints HTTP, documentação Swagger, guards e status codes;
- `*.service.ts`: regras de negócio, autorização multi-tenant e orquestração;
- `repositories/*.repository.ts`: camada de persistência PostgREST;
- `dto/*.dto.ts`: contratos de entrada/saída tipados com `class-validator` e `@nestjs/swagger`;
- `entities/*.entity.ts`: modelos de domínio tipados.
