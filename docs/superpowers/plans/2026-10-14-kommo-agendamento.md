# Integração Kommo → Agendamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quando o lead entra na etapa "agendado" do Kommo, um Salesbot chama `POST /kommo/agendamento/{tenant_token}`; a API grava o evento num outbox e um job assíncrono lê o lead/contato pela API v4, faz upsert do cliente e do agendamento e devolve uma nota no lead.

**Architecture:** Endpoint público e fino (lookup do token por hash SHA-256 + 1 insert no outbox, < 2s). Um worker (`@nestjs/schedule`, roda em todas as instâncias) reivindica eventos via RPC Postgres com `FOR UPDATE SKIP LOCKED` e lease, então é seguro com N réplicas. O upsert do agendamento é atômico numa função SQL com índice único parcial `(company_id, kommo_lead_id) WHERE status='scheduled' AND deleted_at IS NULL`. Nenhum estado compartilhado em memória.

**Tech Stack:** NestJS 12, TypeScript, Supabase/PostgREST (`@supabase/supabase-js` 2.117), Postgres, Vitest, `fetch` nativo do Node 24, `node:crypto`.

**Spec:** decisões da sessão de grill-me de 2026-10-13/14, consolidadas em "Global Constraints" abaixo (esta seção é a spec).

## Global Constraints

- Rota: `POST /kommo/agendamento/:tenantToken`. Token **só na URL** (o bloco "Enviar um webhook" do Salesbot não envia headers).
- Endpoint responde em < 2s: valida token, grava no outbox, responde 200. Nunca chama o Kommo de forma síncrona.
- Aceitar `application/json` e `application/x-www-form-urlencoded` com parsing estendido (`leads[status][0][id]` → objeto aninhado).
- Payload nativo `leads[status]`: só aceitar itens com `status_id` igual ao `scheduled_status_id` da integração (Óticas Zyros: `112039795`). Itens de outras etapas são ignorados (200, nada gravado).
- Data: campo de lead `date_field_id` (Zyros `614091`), Unix timestamp, fuso `America/Araguaina` (UTC−03, sem horário de verão).
- Horário: campo de lead `time_field_id` (Zyros `614093`), texto `HH:MM`.
- Horário vazio/inválido → grava com `scheduled_time_unknown=true`, `scheduled_at` = 00:00 local do dia, `needs_review=true`. Nunca descartar. (`scheduled_at` é `NOT NULL` no schema, por isso 00:00 + flag em vez de `time=null`.)
- Data vazia/inválida → não há dia para gravar: evento `failed` + nota no lead explicando. Não é retentado.
- Conflito de horário **nunca** bloqueia agendamento vindo do Kommo; status sempre `scheduled`.
- Upsert: existe agendamento `scheduled` não deletado com o mesmo `(company_id, kommo_lead_id)` → atualiza (com linha em `appointment_history`). Se só houver `attended`/`no_show`/`cancelled` → cria novo.
- Cliente: busca por `kommo_contact_id`; depois por telefone (com e sem o 9º dígito após o DDD); senão cria. Grava o vínculo `kommo_contact_id`.
- Telefone no formato do schema atual: só dígitos, 10–11 (DDD + número, sem `55`) — `chk_customers_phone_format`. Inválido → `phone=null` + `needs_review=true`, nunca bloqueia.
- Identidade do cliente (Task 0B, `CustomerMatchingService`, usada pelo Kommo e pelo "Comparecer"): `kommo_contact_id` → telefone (com/sem 9º dígito) **e** `similarity(norm(nome)) >= 0.85` → reutiliza; telefone igual e similaridade entre 0.6 e 0.85 → cria novo com `needs_review` ("Possível duplicado de <id>"); senão cria novo. Telefone é compartilhado por famílias, então não há índice único em telefone nem em nome. Nunca merge automático.
- Fora do escopo (issue separada): limpeza de telefones legados no formato `5563xxxxxxxx` e revisão manual dos ~4 grupos com nomes quase iguais.
- Listagem/agenda: `scheduled_time_unknown=true` é exibido como "horário a confirmar", nunca 00:00. A API expõe o campo na resposta; a interface deve usá-lo.
- Indicação: campo de lead `referral_field_id` (Zyros `566124`), opcional → `notes = "Indicação: <valor>"`.
- Telefone do contato: campo `phone_field_id` (Zyros `268220`).
- Pipeline Zyros: `14505231` (guardado para referência).
- Retorno ao Kommo: nota comum no lead (`POST /api/v4/leads/{id}/notes`). O long-lived token da ótica precisa de escopo de escrita.
- Autor dos registros: usuário técnico por empresa (`service_user_id`), com acesso à unidade — os triggers `enforce_*_company_access` exigem isso.
- Credenciais: `tenant_token` guardado como SHA-256 hex; token do Kommo criptografado com AES-256-GCM, chave `KOMMO_ENCRYPTION_KEY` (32 bytes, base64).
- Fora da v1: consulta de horários, reagendar/cancelar pelo chat, aviso de lotação.
- Comentários no código: só curtos e não óbvios (regra permanente do usuário).
- Git: Conventional Commits, branch `feat/kommo-agendamento`, PR obrigatório, nunca push direto na `main`.
- Banco via `this.supabase.getClient().from(...)` — **não** usar `.table(...)`, que não existe no supabase-js 2.117 (ver nota no fim).

## Review Focus

1. **Formato real do payload do Salesbot** — o bloco "Enviar um webhook" pode mandar `leads[status]`, `leads[add]` ou um corpo customizado com `lead_id`; o extrator precisa achar o lead em todos, e o payload bruto fica no outbox para depuração. Testes na Task 2.
2. **Duas réplicas processando ao mesmo tempo** — o mesmo evento não pode ser processado duas vezes; `claim_kommo_events` usa `SKIP LOCKED` e lease (`locked_until`) que expira se a réplica morrer. Validação SQL na Task 1, teste de reentrância na Task 8.
3. **Timestamp de data perto da meia-noite** — o Kommo pode mandar 00:00 local (= 03:00Z) ou 00:00Z (= 21:00 do dia anterior em Araguaína); os dois devem virar o mesmo dia civil. Teste na Task 2.
4. **Token do Kommo revogado/expirado (401)** — não adianta retentar; marcar `failed` direto com `last_error` claro. Testes nas Tasks 6 e 8.
5. **Lead reenviado enquanto o evento anterior ainda processa** — dois eventos do mesmo lead; o upsert atômico em SQL (com tratamento da corrida do `INSERT`) garante um único agendamento `scheduled`. Validação SQL na Task 1.

---

## File Structure

```
db/migrations/0010_kommo_integration.sql          tabelas, colunas, índices, RPCs
src/config/app.config.ts                          + kommoEncryptionKey, kommoWorker*
src/main.ts                                       urlencoded extended
src/app.module.ts                                 + ScheduleModule, KommoModule
src/modules/customers/entities/customer.entity.ts + kommo_contact_id, needs_review; phone nullable
src/modules/customers/  (Task 0B) CustomerMatchingService, matchByPhone, findByKommoContactId, linkKommoContact
src/modules/appointments/entities/appointment.entity.ts    + kommo_lead_id, needs_review, review_reason, scheduled_time_unknown
src/modules/appointments/repositories/appointment.repository.ts + upsertFromKommo
src/modules/kommo/
  kommo.module.ts
  (telefone: src/common/utils/phone.util.ts, criado na Task 0B)
  utils/kommo-schedule.util.ts     (+ .spec.ts)  data/hora → scheduled_at
  utils/kommo-payload.util.ts      (+ .spec.ts)  extrai lead ids do payload
  kommo-crypto.service.ts          (+ .spec.ts)  sha256 do tenant token, AES-GCM do token Kommo
  entities/kommo-integration.entity.ts
  entities/kommo-event.entity.ts
  repositories/kommo-integration.repository.ts
  repositories/kommo-event.repository.ts
  kommo-webhook.controller.ts
  kommo-webhook.service.ts         (+ .spec.ts)  ingestão (endpoint)
  kommo-client.ts                  (+ .spec.ts)  API v4: lead, contato, nota
  kommo-event-processor.service.ts (+ .spec.ts)  processa 1 evento
  kommo-worker.service.ts          (+ .spec.ts)  intervalo: claim + process + retry
  kommo-admin.controller.ts
  kommo-admin.service.ts           (+ .spec.ts)  criar/atualizar/rotacionar integração (super_admin)
  dto/kommo-integration.dto.ts
docs/KOMMO.md                                     setup e operação
```

---

### Task 0: Pré-requisitos (feitos antes deste plano, fora da branch do Kommo)

1. PR separado com a reescrita NestJS que estava sem commit na `main`.
2. PR `fix`: `.table()` → `.from()` nos repositórios existentes.
3. Com os dois mesclados, criar a branch a partir da `main` atualizada:

```bash
git checkout main && git pull && git checkout -b feat/kommo-agendamento
```

---

### Task 0B: Identificação de cliente por telefone + similaridade de nome

Telefone é compartilhado por famílias (123 grupos em produção, todos com nomes distintos), então telefone sozinho **não** identifica o cliente. Regra única, usada pelo Kommo (Task 7) e pelo "Comparecer" (`promoteLeadToCustomer`):

1. `kommo_contact_id` (só Kommo; coluna criada na Task 1) → reutiliza.
2. Candidatos com o mesmo telefone (com/sem 9º dígito), pontuados por `similarity(norm(full_name), norm(nome))`, `norm = lower(unaccent(trim(x)))`:
   - melhor score `>= 0.85` → reutiliza esse cliente;
   - melhor score `>= 0.6` e `< 0.85` → cria cliente novo com `needs_review=true`, `review_reason = 'Possível duplicado de <id>'`;
   - senão (ou sem telefone) → cria cliente novo.
3. Nunca faz merge automático.

**Files:**
- Create: `db/migrations/0009_customer_matching.sql`
- Create: `src/common/utils/phone.util.ts`, `phone.util.spec.ts` (código e testes da seção "telefone" da Task 2)
- Create: `src/modules/customers/customer-matching.ts`, `customer-matching.spec.ts`
- Create: `src/modules/customers/customer-matching.service.ts`, `customer-matching.service.spec.ts`
- Modify: `src/modules/customers/entities/customer.entity.ts`, `repositories/customer.repository.ts`, `customers.module.ts`
- Modify: `src/modules/appointments/appointments.service.ts` (`promoteLeadToCustomer`), `appointments.service.spec.ts`

**Interfaces:**
- Produces:
  - `normalizePhone`, `phoneVariants` em `@/common/utils/phone.util`.
  - `type CustomerCandidate = { id: string; score: number }`
  - `classifyCustomerMatch(candidates: CustomerCandidate[]): { kind: 'reuse'; id: string } | { kind: 'possible_duplicate'; id: string } | { kind: 'new' }`
  - `CustomerRepository.matchByPhone(companyId: string, phones: string[], fullName: string): Promise<CustomerCandidate[]>`
  - `CustomerRepository.findByKommoContactId(companyId: string, contactId: number): Promise<Customer | null>`
  - `CustomerRepository.linkKommoContact(customerId: string, contactId: number, userId: string): Promise<void>`
  - `CustomerMatchingService.resolve(input: ResolveCustomerInput): Promise<ResolvedCustomer>`

```ts
export interface ResolveCustomerInput {
  companyId: string;
  companyUnitId: string;
  userId: string;
  fullName: string;
  phone: string | null; // já normalizado (normalizePhone)
  kommoContactId?: number | null;
}
export interface ResolvedCustomer {
  customerId: string;
  created: boolean;
  reviewReason: string | null; // 'Possível duplicado de <id>' ou null
}
```

- [ ] **Step 1: Migration `0009_customer_matching.sql`**

Antes de escrever, rodar `\dx` no banco: se as extensões existentes ficam no schema `extensions` (padrão Supabase), usar `WITH SCHEMA extensions` e manter `extensions` no `search_path` da função; senão, criar em `public` e ajustar o `search_path`.

```sql
-- Telefone é compartilhado por famílias: identidade = telefone + similaridade de nome.
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
```

No fim do arquivo, aplicar à função o mesmo padrão de `REVOKE`/`GRANT` usado em `0002_security_hardening.sql`/`0003_restore_service_role_access.sql` para `update_appointment_with_history`.

Aplicar em local/staging e validar:

```sql
SELECT similarity(lower(unaccent('José Antônio')), lower(unaccent('jose antonio')));          -- 1
SELECT similarity(lower(unaccent('Maria da Silva')), lower(unaccent('Mariana da Silva')));    -- anotar o valor
SELECT similarity(lower(unaccent('Maria da Silva')), lower(unaccent('João da Silva')));       -- deve ficar < 0.85
```

Anotar os valores no PR: se "João da Silva" × "Maria da Silva" (pai/filha, mesmo sobrenome) passar de 0.6, avisar o usuário — vai gerar flag de possível duplicado em famílias.

- [ ] **Step 2: Testes que falham — regra pura e telefone**

`customer-matching.spec.ts`:

```ts
import { classifyCustomerMatch } from './customer-matching';

describe('classifyCustomerMatch', () => {
  it('sem candidatos → novo', () => {
    expect(classifyCustomerMatch([])).toEqual({ kind: 'new' });
  });

  it.each([0.85, 0.97, 1])('score %s → reutiliza', (score) => {
    expect(classifyCustomerMatch([{ id: 'a', score }])).toEqual({ kind: 'reuse', id: 'a' });
  });

  it.each([0.6, 0.7, 0.849])('score %s → possível duplicado', (score) => {
    expect(classifyCustomerMatch([{ id: 'a', score }])).toEqual({
      kind: 'possible_duplicate',
      id: 'a',
    });
  });

  it.each([0, 0.3, 0.599])('score %s → novo (outro membro da família)', (score) => {
    expect(classifyCustomerMatch([{ id: 'a', score }])).toEqual({ kind: 'new' });
  });

  it('usa o melhor candidato mesmo fora de ordem', () => {
    expect(
      classifyCustomerMatch([
        { id: 'pai', score: 0.2 },
        { id: 'filha', score: 0.9 },
      ]),
    ).toEqual({ kind: 'reuse', id: 'filha' });
  });
});
```

`src/common/utils/phone.util.spec.ts`: os testes da seção "telefone" da Task 2, mais:

```ts
  it('12 dígitos começando com 55 perde o código do país', () => {
    expect(normalizePhone('556391234567')).toBe('6391234567');
  });

  it('11 dígitos começando com 55 é DDD 55, não código do país', () => {
    expect(normalizePhone('55991234567')).toBe('55991234567');
  });
```

- [ ] **Step 3: Testes que falham — serviço**

`customer-matching.service.spec.ts`:

```ts
import { ConflictException } from '@nestjs/common';
import { CustomerMatchingService } from './customer-matching.service';

describe('CustomerMatchingService', () => {
  let repo: any;
  let service: CustomerMatchingService;
  const base = {
    companyId: 'comp-1',
    companyUnitId: 'unit-1',
    userId: 'u-1',
    fullName: 'Maria da Silva',
    phone: '63991234567',
  };

  beforeEach(() => {
    repo = {
      findByKommoContactId: vi.fn().mockResolvedValue(null),
      matchByPhone: vi.fn().mockResolvedValue([]),
      create: vi.fn().mockResolvedValue({ id: 'cust-new' }),
      linkKommoContact: vi.fn().mockResolvedValue(undefined),
    };
    service = new CustomerMatchingService(repo);
  });

  it('kommo_contact_id vence tudo', async () => {
    repo.findByKommoContactId.mockResolvedValue({ id: 'cust-k' });
    await expect(service.resolve({ ...base, kommoContactId: 9 })).resolves.toEqual({
      customerId: 'cust-k',
      created: false,
      reviewReason: null,
    });
    expect(repo.matchByPhone).not.toHaveBeenCalled();
  });

  it('telefone + nome parecido (>= 0.85) reutiliza e vincula o contato', async () => {
    repo.matchByPhone.mockResolvedValue([{ id: 'cust-m', score: 0.92 }]);
    await expect(service.resolve({ ...base, kommoContactId: 9 })).resolves.toEqual({
      customerId: 'cust-m',
      created: false,
      reviewReason: null,
    });
    expect(repo.matchByPhone).toHaveBeenCalledWith(
      'comp-1',
      ['63991234567', '6391234567'],
      'Maria da Silva',
    );
    expect(repo.linkKommoContact).toHaveBeenCalledWith('cust-m', 9, 'u-1');
    expect(repo.create).not.toHaveBeenCalled();
  });

  it('mesmo telefone, outro membro da família (< 0.6) → cria sem revisão', async () => {
    repo.matchByPhone.mockResolvedValue([{ id: 'cust-pai', score: 0.2 }]);
    await expect(service.resolve(base)).resolves.toEqual({
      customerId: 'cust-new',
      created: true,
      reviewReason: null,
    });
    expect(repo.create).toHaveBeenCalledWith({
      company_id: 'comp-1',
      company_unit_id: 'unit-1',
      full_name: 'Maria da Silva',
      phone: '63991234567',
      kommo_contact_id: null,
      needs_review: false,
      review_reason: null,
      created_by_user_id: 'u-1',
      updated_by_user_id: 'u-1',
    });
  });

  it('nome quase igual (0.6–0.85) → cria com possível duplicado', async () => {
    repo.matchByPhone.mockResolvedValue([{ id: 'cust-x', score: 0.7 }]);
    await expect(service.resolve(base)).resolves.toEqual({
      customerId: 'cust-new',
      created: true,
      reviewReason: 'Possível duplicado de cust-x',
    });
    expect(repo.create).toHaveBeenCalledWith(
      expect.objectContaining({ needs_review: true, review_reason: 'Possível duplicado de cust-x' }),
    );
  });

  it('sem telefone → cria direto, sem buscar candidatos', async () => {
    await service.resolve({ ...base, phone: null });
    expect(repo.matchByPhone).not.toHaveBeenCalled();
    expect(repo.create).toHaveBeenCalledWith(expect.objectContaining({ phone: null }));
  });

  it('corrida no kommo_contact_id: usa o cliente que venceu', async () => {
    repo.create.mockRejectedValue(new ConflictException('x'));
    repo.findByKommoContactId.mockResolvedValueOnce(null).mockResolvedValueOnce({ id: 'cust-race' });
    await expect(service.resolve({ ...base, kommoContactId: 9 })).resolves.toEqual({
      customerId: 'cust-race',
      created: false,
      reviewReason: null,
    });
  });

  it('conflito sem contato Kommo propaga', async () => {
    repo.create.mockRejectedValue(new ConflictException('x'));
    await expect(service.resolve(base)).rejects.toBeInstanceOf(ConflictException);
  });
});
```

- [ ] **Step 4:** Run `npx vitest run src/common/utils src/modules/customers` → FAIL.

- [ ] **Step 5: Implementar**

`src/common/utils/phone.util.ts`: código da seção "telefone" da Task 2 (só remove `55` com 12–13 dígitos; nunca grava `55` + 9 dígitos sem DDD).

`src/modules/customers/customer-matching.ts`:

```ts
export type CustomerCandidate = { id: string; score: number };

export type CustomerMatch =
  | { kind: 'reuse'; id: string }
  | { kind: 'possible_duplicate'; id: string }
  | { kind: 'new' };

export const SAME_PERSON_THRESHOLD = 0.85;
export const POSSIBLE_DUPLICATE_THRESHOLD = 0.6;

export function classifyCustomerMatch(candidates: CustomerCandidate[]): CustomerMatch {
  const best = candidates.reduce<CustomerCandidate | null>(
    (acc, c) => (!acc || c.score > acc.score ? c : acc),
    null,
  );
  if (!best) return { kind: 'new' };
  if (best.score >= SAME_PERSON_THRESHOLD) return { kind: 'reuse', id: best.id };
  if (best.score >= POSSIBLE_DUPLICATE_THRESHOLD) return { kind: 'possible_duplicate', id: best.id };
  return { kind: 'new' };
}
```

`src/modules/customers/customer-matching.service.ts`:

```ts
import { ConflictException, Injectable } from '@nestjs/common';
import { phoneVariants } from '@/common/utils/phone.util';
import { classifyCustomerMatch } from './customer-matching';
import { CustomerRepository } from './repositories/customer.repository';

export interface ResolveCustomerInput {
  companyId: string;
  companyUnitId: string;
  userId: string;
  fullName: string;
  phone: string | null;
  kommoContactId?: number | null;
}

export interface ResolvedCustomer {
  customerId: string;
  created: boolean;
  reviewReason: string | null;
}

@Injectable()
export class CustomerMatchingService {
  constructor(private readonly repo: CustomerRepository) {}

  async resolve(input: ResolveCustomerInput): Promise<ResolvedCustomer> {
    const contactId = input.kommoContactId ?? null;

    if (contactId) {
      const linked = await this.repo.findByKommoContactId(input.companyId, contactId);
      if (linked) return { customerId: linked.id, created: false, reviewReason: null };
    }

    const match = input.phone
      ? classifyCustomerMatch(
          await this.repo.matchByPhone(input.companyId, phoneVariants(input.phone), input.fullName),
        )
      : ({ kind: 'new' } as const);

    if (match.kind === 'reuse') {
      if (contactId) await this.repo.linkKommoContact(match.id, contactId, input.userId);
      return { customerId: match.id, created: false, reviewReason: null };
    }

    const reviewReason =
      match.kind === 'possible_duplicate' ? `Possível duplicado de ${match.id}` : null;
    try {
      const created = await this.repo.create({
        company_id: input.companyId,
        company_unit_id: input.companyUnitId,
        full_name: input.fullName,
        phone: input.phone,
        kommo_contact_id: contactId,
        needs_review: reviewReason !== null,
        review_reason: reviewReason,
        created_by_user_id: input.userId,
        updated_by_user_id: input.userId,
      });
      return { customerId: created.id, created: true, reviewReason };
    } catch (err) {
      // O único índice único restante em customers é o do contato Kommo: outro evento venceu a corrida.
      if (err instanceof ConflictException && contactId) {
        const winner = await this.repo.findByKommoContactId(input.companyId, contactId);
        if (winner) return { customerId: winner.id, created: false, reviewReason: null };
      }
      throw err;
    }
  }
}
```

`customer.entity.ts`: `phone: string | null;` e adicionar `kommo_contact_id: number | null; needs_review: boolean; review_reason: string | null;`.

`customer.repository.ts`:
- remover `getByIdentity`;
- em `create`, remover `kommo_contact_id` do payload quando for `null`/`undefined` (a coluna só existe depois da `0010`); trocar a mensagem de conflito de `create` e `update` para `'Este contato do Kommo já está vinculado a outro cliente'`;
- adicionar:

```ts
  async matchByPhone(
    companyId: string,
    phones: string[],
    fullName: string,
  ): Promise<{ id: string; score: number }[]> {
    const { data, error } = await this.db.rpc('match_customers_by_phone', {
      p_company_id: companyId,
      p_phones: phones,
      p_full_name: fullName,
    });
    if (error) throw error;
    return (data || []).map((row: any) => ({ id: row.id, score: Number(row.score) }));
  }

  async findByKommoContactId(companyId: string, contactId: number): Promise<Customer | null> {
    const { data, error } = await this.db
      .from(TABLE)
      .select('*')
      .eq('company_id', companyId)
      .eq('kommo_contact_id', contactId)
      .is('deleted_at', null)
      .maybeSingle();
    if (error) throw error;
    return data ? new Customer(data) : null;
  }

  async linkKommoContact(customerId: string, contactId: number, userId: string): Promise<void> {
    const { error } = await this.db
      .from(TABLE)
      .update({ kommo_contact_id: contactId, updated_by_user_id: userId })
      .eq('id', customerId)
      .is('kommo_contact_id', null);
    if (error && error.code !== UNIQUE_VIOLATION) throw error;
  }
```

`customers.module.ts`: adicionar `CustomerMatchingService` em `providers` e `exports`.

`appointments.service.ts`: importar `normalizePhone` de `@/common/utils/phone.util` e `CustomerMatchingService`; injetá-lo no construtor como `private readonly customerMatching: CustomerMatchingService` (último parâmetro); trocar `promoteLeadToCustomer` por:

```ts
  private async promoteLeadToCustomer(
    appointment: Appointment,
    currentUser: User,
  ): Promise<string> {
    const { customerId } = await this.customerMatching.resolve({
      companyId: appointment.company_id,
      companyUnitId: appointment.company_unit_id,
      userId: currentUser.id,
      fullName: appointment.lead_full_name,
      phone: normalizePhone(appointment.lead_phone),
    });
    return customerId;
  }
```

Remover imports que ficarem sem uso (ex.: `ConflictException`, se não for mais usado no arquivo).

- [ ] **Step 6: Ajustar `appointments.service.spec.ts`** — criar `mockCustomerMatching = { resolve: vi.fn().mockResolvedValue({ customerId: 'new-cust-1', created: true, reviewReason: null }) }`, passá-lo como último argumento do construtor e remover do mock de cliente o que só servia ao `promoteLeadToCustomer`. No teste de comparecimento existente, trocar as asserções sobre `getByIdentity`/`create` por uma asserção de `mockCustomerMatching.resolve` com `companyId`, `companyUnitId`, `userId`, `fullName` e `phone` (o `lead_phone` do teste já normalizado). Duplicar esse teste com `lead_phone: '+55 63 9123-4567'`, esperando `phone: '6391234567'`.

- [ ] **Step 7:** Run `npx vitest run && npx tsc --noEmit` → PASS.

- [ ] **Step 8: Commit**

```bash
git add db/migrations/0009_customer_matching.sql src/common/utils/phone.util.ts src/common/utils/phone.util.spec.ts src/modules/customers src/modules/appointments
git commit -m "feat(customers): identificar cliente por telefone + similaridade de nome"
```

---

### Task 1: Migration 0010 (Kommo)

**Files:**
- Create: `db/migrations/0010_kommo_integration.sql`

**Interfaces:**
- Produces: tabelas `kommo_integrations`, `kommo_events`; colunas novas em `customers` e `appointments`; RPCs `claim_kommo_events(p_limit INT, p_lease_seconds INT) RETURNS SETOF kommo_events` e `upsert_kommo_appointment(...) RETURNS SETOF appointments` (parâmetros abaixo, usados na Task 4).

- [ ] **Step 1: Escrever a migration**

```sql
-- Integração Kommo: config por empresa, outbox de eventos e vínculo de leads/contatos.

CREATE TABLE kommo_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies (id),
    company_unit_id UUID NOT NULL REFERENCES company_units (id),
    -- Autor dos registros; precisa de acesso à unidade (triggers de customers/appointments).
    service_user_id UUID NOT NULL REFERENCES users (id),
    subdomain VARCHAR(100) NOT NULL,
    access_token_encrypted TEXT NOT NULL,
    tenant_token_hash CHAR(64) NOT NULL,
    pipeline_id BIGINT NOT NULL,
    scheduled_status_id BIGINT NOT NULL,
    date_field_id BIGINT NOT NULL,
    time_field_id BIGINT NOT NULL,
    referral_field_id BIGINT,
    phone_field_id BIGINT NOT NULL,
    timezone VARCHAR(64) NOT NULL DEFAULT 'America/Araguaina',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at TIMESTAMPTZ,
    CONSTRAINT chk_kommo_integrations_subdomain CHECK (subdomain ~ '^[a-z0-9-]+$')
);

CREATE UNIQUE INDEX uq_kommo_integrations_company
ON kommo_integrations (company_id) WHERE deleted_at IS NULL;
CREATE UNIQUE INDEX uq_kommo_integrations_tenant_token_hash
ON kommo_integrations (tenant_token_hash);

CREATE TYPE kommo_event_status AS ENUM ('pending', 'processing', 'done', 'failed');

CREATE TABLE kommo_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    integration_id UUID NOT NULL REFERENCES kommo_integrations (id),
    company_id UUID NOT NULL REFERENCES companies (id),
    kommo_lead_id BIGINT NOT NULL,
    payload JSONB NOT NULL,
    status kommo_event_status NOT NULL DEFAULT 'pending',
    attempts INT NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_until TIMESTAMPTZ,
    last_error TEXT,
    appointment_id UUID REFERENCES appointments (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX idx_kommo_events_claimable
ON kommo_events (next_attempt_at) WHERE status IN ('pending', 'processing');
CREATE INDEX idx_kommo_events_lead ON kommo_events (company_id, kommo_lead_id);

-- needs_review/review_reason de customers já vêm da 0009.
ALTER TABLE customers ADD COLUMN kommo_contact_id BIGINT;

CREATE UNIQUE INDEX uq_customers_company_kommo_contact
ON customers (company_id, kommo_contact_id)
WHERE kommo_contact_id IS NOT NULL AND deleted_at IS NULL;

ALTER TABLE appointments
    ADD COLUMN kommo_lead_id BIGINT,
    ADD COLUMN needs_review BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN review_reason TEXT,
    ADD COLUMN scheduled_time_unknown BOOLEAN NOT NULL DEFAULT FALSE;

CREATE UNIQUE INDEX uq_appointments_company_kommo_lead_scheduled
ON appointments (company_id, kommo_lead_id)
WHERE kommo_lead_id IS NOT NULL AND status = 'scheduled' AND deleted_at IS NULL;

-- Agendamentos do Kommo não podem ser barrados por conflito de horário (atendimento por ordem de chegada).
DROP INDEX uq_appointments_customer_scheduled_at;
CREATE UNIQUE INDEX uq_appointments_customer_scheduled_at
ON appointments (customer_id, scheduled_at)
WHERE deleted_at IS NULL AND kommo_lead_id IS NULL;

DROP INDEX uq_appointments_lead_scheduled_at;
CREATE UNIQUE INDEX uq_appointments_lead_scheduled_at
ON appointments (company_id, lead_full_name, scheduled_at)
WHERE customer_id IS NULL AND deleted_at IS NULL AND kommo_lead_id IS NULL;

-- Evento 'processing' com lease vencido volta a ser reivindicável (réplica morreu no meio).
CREATE OR REPLACE FUNCTION claim_kommo_events(p_limit INT, p_lease_seconds INT)
RETURNS SETOF kommo_events
LANGUAGE plpgsql
SET search_path = public
AS $$
BEGIN
    RETURN QUERY
    UPDATE kommo_events e
    SET status = 'processing',
        attempts = e.attempts + 1,
        locked_until = now() + make_interval(secs => p_lease_seconds)
    WHERE e.id IN (
        SELECT id FROM kommo_events
        WHERE next_attempt_at <= now()
          AND (status = 'pending' OR (status = 'processing' AND locked_until < now()))
        ORDER BY next_attempt_at
        LIMIT p_limit
        FOR UPDATE SKIP LOCKED
    )
    RETURNING e.*;
END;
$$;

CREATE OR REPLACE FUNCTION upsert_kommo_appointment(
    p_company_id UUID,
    p_company_unit_id UUID,
    p_user_id UUID,
    p_kommo_lead_id BIGINT,
    p_customer_id UUID,
    p_lead_full_name VARCHAR,
    p_lead_phone VARCHAR,
    p_scheduled_at TIMESTAMPTZ,
    p_scheduled_time_unknown BOOLEAN,
    p_notes TEXT,
    p_needs_review BOOLEAN,
    p_review_reason TEXT
)
RETURNS SETOF appointments
LANGUAGE plpgsql
SET search_path = public
AS $$
DECLARE
    v_old appointments;
    v_new appointments;
BEGIN
    SELECT * INTO v_old FROM appointments
    WHERE company_id = p_company_id
      AND kommo_lead_id = p_kommo_lead_id
      AND status = 'scheduled'
      AND deleted_at IS NULL
    FOR UPDATE;

    IF NOT FOUND THEN
        INSERT INTO appointments (
            company_id, company_unit_id, customer_id, lead_full_name, lead_phone,
            created_by_user_id, scheduled_at, status, notes,
            kommo_lead_id, needs_review, review_reason, scheduled_time_unknown
        ) VALUES (
            p_company_id, p_company_unit_id, p_customer_id, p_lead_full_name, p_lead_phone,
            p_user_id, p_scheduled_at, 'scheduled', p_notes,
            p_kommo_lead_id, p_needs_review, p_review_reason, p_scheduled_time_unknown
        )
        ON CONFLICT (company_id, kommo_lead_id)
            WHERE kommo_lead_id IS NOT NULL AND status = 'scheduled' AND deleted_at IS NULL
        DO NOTHING
        RETURNING * INTO v_new;

        IF v_new.id IS NOT NULL THEN
            RETURN NEXT v_new;
            RETURN;
        END IF;

        -- Corrida: outra transação inseriu entre o SELECT e o INSERT; atualiza a linha dela.
        SELECT * INTO v_old FROM appointments
        WHERE company_id = p_company_id AND kommo_lead_id = p_kommo_lead_id
          AND status = 'scheduled' AND deleted_at IS NULL
        FOR UPDATE;
    END IF;

    UPDATE appointments SET
        customer_id = COALESCE(p_customer_id, customer_id),
        lead_full_name = p_lead_full_name,
        lead_phone = p_lead_phone,
        scheduled_at = p_scheduled_at,
        scheduled_time_unknown = p_scheduled_time_unknown,
        notes = p_notes,
        needs_review = p_needs_review,
        review_reason = p_review_reason,
        updated_by_user_id = p_user_id
    WHERE id = v_old.id
    RETURNING * INTO v_new;

    INSERT INTO appointment_history (
        appointment_id, changed_by_user_id,
        previous_scheduled_at, new_scheduled_at,
        previous_status, new_status,
        previous_notes, new_notes
    ) VALUES (
        v_new.id, p_user_id,
        v_old.scheduled_at, v_new.scheduled_at,
        v_old.status, v_new.status,
        v_old.notes, v_new.notes
    );

    RETURN NEXT v_new;
END;
$$;
```

- [ ] **Step 2: Grants/RLS no padrão do projeto** — abrir `db/migrations/0002_security_hardening.sql` e `0003_restore_service_role_access.sql` e replicar, no fim da `0010`, exatamente o mesmo padrão usado para `appointments` e `update_appointment_with_history` (RLS, `REVOKE` de `anon`/`authenticated`, `GRANT` para `service_role`) nas duas tabelas e nas duas funções novas.

- [ ] **Step 3: Aplicar em banco local/staging e validar**

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/0010_kommo_integration.sql
```

Review Focus 2 — em duas sessões `psql` simultâneas, com eventos `pending` de teste inseridos:

```sql
-- sessão A
BEGIN; SELECT id FROM claim_kommo_events(10, 120);
-- sessão B, antes do COMMIT de A: não pode retornar os mesmos ids
SELECT id FROM claim_kommo_events(10, 120);
```

Review Focus 5 e regra de unicidade parcial:

```sql
-- 2× com o mesmo lead (999) → 1 linha scheduled e 1 linha nova em appointment_history
SELECT count(*) FROM appointments WHERE kommo_lead_id = 999 AND status = 'scheduled';  -- 1
-- UPDATE ... SET status = 'attended' nessa linha e chamar de novo → nova linha scheduled
SELECT status, count(*) FROM appointments WHERE kommo_lead_id = 999 GROUP BY status;   -- attended 1, scheduled 1
-- dois leads diferentes, mesmo cliente e mesmo scheduled_at → ambos inseridos (sem 23505)
```

Expected: contagens acima. Desfazer os dados de teste.

- [ ] **Step 4: Commit**

```bash
git add db/migrations/0010_kommo_integration.sql
git commit -m "feat(kommo): adicionar schema de integração, outbox e upsert de agendamento"
```

---

### Task 2: Utilitários puros (telefone, data/hora, payload)

**Files:**
- Telefone: `src/common/utils/phone.util.ts` + `.spec.ts` são **criados na Task 0B** com o código e os testes abaixo (seção "telefone"); nesta task só conferir que existem.
- Create: `src/modules/kommo/utils/kommo-schedule.util.ts`, `kommo-schedule.util.spec.ts`
- Create: `src/modules/kommo/utils/kommo-payload.util.ts`, `kommo-payload.util.spec.ts`

**Interfaces:**
- Produces:
  - `normalizePhone(raw: string | null | undefined): string | null` — 10/11 dígitos sem `55`, ou `null`.
  - `phoneVariants(normalized: string): string[]` — o próprio + com/sem o 9º dígito.
  - `type ScheduleResult = { ok: true; scheduledAt: string; timeUnknown: boolean } | { ok: false; reason: string }`
  - `parseSchedule(dateUnix: unknown, time: unknown, timezone: string): ScheduleResult` — `scheduledAt` no formato `YYYY-MM-DDTHH:MM:00-03:00`.
  - `extractLeadIds(body: unknown, scheduledStatusId: number): number[]`

- [ ] **Step 1: Testes que falham**

`src/common/utils/phone.util.spec.ts` (Task 0B):

```ts
import { normalizePhone, phoneVariants } from './phone.util';

describe('normalizePhone', () => {
  it.each([
    ['+55 (63) 99123-4567', '63991234567'],
    ['5563991234567', '63991234567'],
    ['63 3215-1234', '6332151234'],
    ['(63) 9123-4567', '6391234567'],
    ['055 63 99123 4567', '63991234567'],
  ])('%s → %s', (raw, expected) => {
    expect(normalizePhone(raw)).toBe(expected);
  });

  it.each([null, undefined, '', 'abc', '12345', '+1 415 555 0100 99'])(
    'retorna null para %s',
    (raw) => {
      expect(normalizePhone(raw as any)).toBeNull();
    },
  );
});

describe('phoneVariants', () => {
  it('celular com 9 também gera sem 9', () => {
    expect(phoneVariants('63991234567')).toEqual(['63991234567', '6391234567']);
  });

  it('celular sem 9 também gera com 9', () => {
    expect(phoneVariants('6391234567')).toEqual(['6391234567', '63991234567']);
  });

  it('fixo não ganha variante', () => {
    expect(phoneVariants('6332151234')).toEqual(['6332151234']);
  });
});
```

`kommo-schedule.util.spec.ts`:

```ts
import { parseSchedule } from './kommo-schedule.util';

const TZ = 'America/Araguaina';
// 2026-10-20 00:00 em Araguaína (UTC-3) = 2026-10-20T03:00:00Z
const LOCAL_MIDNIGHT = Date.UTC(2026, 9, 20, 3) / 1000;
// 2026-10-20 00:00Z = 2026-10-19 21:00 local
const UTC_MIDNIGHT = Date.UTC(2026, 9, 20, 0) / 1000;

describe('parseSchedule', () => {
  it('combina data local e HH:MM', () => {
    expect(parseSchedule(LOCAL_MIDNIGHT, '14:30', TZ)).toEqual({
      ok: true,
      scheduledAt: '2026-10-20T14:30:00-03:00',
      timeUnknown: false,
    });
  });

  it('aceita timestamp como string e H:MM', () => {
    expect(parseSchedule(String(LOCAL_MIDNIGHT), '8:05', TZ)).toEqual({
      ok: true,
      scheduledAt: '2026-10-20T08:05:00-03:00',
      timeUnknown: false,
    });
  });

  it('timestamp de meia-noite UTC continua sendo o mesmo dia civil', () => {
    expect(parseSchedule(UTC_MIDNIGHT, '09:00', TZ)).toMatchObject({
      scheduledAt: '2026-10-20T09:00:00-03:00',
    });
  });

  it.each([null, '', '25:00', '14h30', '14:7', 'manhã'])(
    'horário %s → 00:00 e timeUnknown',
    (time) => {
      expect(parseSchedule(LOCAL_MIDNIGHT, time, TZ)).toEqual({
        ok: true,
        scheduledAt: '2026-10-20T00:00:00-03:00',
        timeUnknown: true,
      });
    },
  );

  it.each([null, '', 'amanhã', 0, -5])('data %s → erro', (date) => {
    expect(parseSchedule(date, '10:00', TZ)).toEqual({
      ok: false,
      reason: 'Data do agendamento vazia ou inválida',
    });
  });
});
```

`kommo-payload.util.spec.ts`:

```ts
import { extractLeadIds } from './kommo-payload.util';

const STAGE = 112039795;

describe('extractLeadIds', () => {
  it('webhook nativo leads[status] filtra pela etapa', () => {
    const body = {
      leads: {
        status: [
          { id: '111', status_id: String(STAGE), pipeline_id: '14505231' },
          { id: '222', status_id: '999' },
        ],
      },
    };
    expect(extractLeadIds(body, STAGE)).toEqual([111]);
  });

  it('aceita objeto indexado ({"0": {...}}) vindo do urlencoded', () => {
    const body = { leads: { status: { '0': { id: '111', status_id: String(STAGE) } } } };
    expect(extractLeadIds(body, STAGE)).toEqual([111]);
  });

  it('leads[add] sem status_id é aceito', () => {
    expect(extractLeadIds({ leads: { add: [{ id: '333' }] } }, STAGE)).toEqual([333]);
  });

  it('corpo customizado com lead_id', () => {
    expect(extractLeadIds({ lead_id: '444' }, STAGE)).toEqual([444]);
  });

  it('remove duplicados', () => {
    const body = { lead_id: '5', leads: { status: [{ id: '5', status_id: String(STAGE) }] } };
    expect(extractLeadIds(body, STAGE)).toEqual([5]);
  });

  it.each([null, {}, { lead_id: 'abc' }, { leads: 'x' }])('payload %j → []', (body) => {
    expect(extractLeadIds(body, STAGE)).toEqual([]);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npx vitest run src/modules/kommo/utils`
Expected: FAIL — módulos não existem.

- [ ] **Step 3: Implementar**

`src/common/utils/phone.util.ts` (Task 0B):

```ts
export function normalizePhone(raw: string | null | undefined): string | null {
  if (!raw) return null;
  let digits = String(raw).replace(/\D/g, '').replace(/^0+/, '');
  if ((digits.length === 12 || digits.length === 13) && digits.startsWith('55')) {
    digits = digits.slice(2);
  }
  return /^[1-9][0-9]{9,10}$/.test(digits) ? digits : null;
}

// Celular brasileiro: o 9º dígito pode faltar em cadastros antigos ou no WhatsApp.
export function phoneVariants(normalized: string): string[] {
  const ddd = normalized.slice(0, 2);
  const rest = normalized.slice(2);
  if (rest.length === 9 && rest.startsWith('9')) {
    return [normalized, ddd + rest.slice(1)];
  }
  if (rest.length === 8 && /^[6-9]/.test(rest)) {
    return [normalized, `${ddd}9${rest}`];
  }
  return [normalized];
}
```

`kommo-schedule.util.ts`:

```ts
export type ScheduleResult =
  | { ok: true; scheduledAt: string; timeUnknown: boolean }
  | { ok: false; reason: string };

const TIME_RE = /^([01]?\d|2[0-3]):([0-5]\d)$/;

function offsetFor(date: Date, timezone: string): string {
  const name = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    timeZoneName: 'longOffset',
  })
    .formatToParts(date)
    .find((p) => p.type === 'timeZoneName')!.value;
  const offset = name.replace('GMT', '');
  return offset === '' ? '+00:00' : offset;
}

function localDay(date: Date, timezone: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}

export function parseSchedule(
  dateUnix: unknown,
  time: unknown,
  timezone: string,
): ScheduleResult {
  const seconds = Number(dateUnix);
  if (dateUnix === null || dateUnix === '' || !Number.isFinite(seconds) || seconds <= 0) {
    return { ok: false, reason: 'Data do agendamento vazia ou inválida' };
  }

  const instant = new Date(seconds * 1000);
  // Campo data às vezes vem como 00:00Z, que cai no dia anterior em UTC-3.
  const isUtcMidnight = instant.getUTCHours() === 0 && instant.getUTCMinutes() === 0;
  const day = isUtcMidnight
    ? instant.toISOString().slice(0, 10)
    : localDay(instant, timezone);

  const match = typeof time === 'string' ? TIME_RE.exec(time.trim()) : null;
  const hhmm = match ? `${match[1].padStart(2, '0')}:${match[2]}` : '00:00';

  return {
    ok: true,
    scheduledAt: `${day}T${hhmm}:00${offsetFor(new Date(`${day}T12:00:00Z`), timezone)}`,
    timeUnknown: !match,
  };
}
```

`kommo-payload.util.ts`:

```ts
function toLeadId(value: unknown): number | null {
  const n = Number(value);
  return Number.isSafeInteger(n) && n > 0 ? n : null;
}

// O parser urlencoded pode gerar {"0": {...}} em vez de array.
function asArray(value: unknown): Record<string, any>[] {
  if (Array.isArray(value)) return value;
  if (value && typeof value === 'object') return Object.values(value);
  return [];
}

export function extractLeadIds(body: unknown, scheduledStatusId: number): number[] {
  if (!body || typeof body !== 'object') return [];
  const b = body as Record<string, any>;
  const ids: number[] = [];

  const direct = toLeadId(b.lead_id ?? b.leadId);
  if (direct) ids.push(direct);

  const leads = b.leads && typeof b.leads === 'object' ? b.leads : {};
  for (const item of asArray(leads.status)) {
    if (Number(item.status_id) !== scheduledStatusId) continue;
    const id = toLeadId(item.id);
    if (id) ids.push(id);
  }
  for (const item of asArray(leads.add)) {
    if (item.status_id !== undefined && Number(item.status_id) !== scheduledStatusId) continue;
    const id = toLeadId(item.id);
    if (id) ids.push(id);
  }

  return [...new Set(ids)];
}
```

- [ ] **Step 4: Rodar e ver passar**

Run: `npx vitest run src/modules/kommo/utils`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/modules/kommo/utils
git commit -m "feat(kommo): normalizar telefone, data/hora e extrair leads do payload"
```

---

### Task 3: Criptografia e config

**Files:**
- Modify: `src/config/app.config.ts`
- Create: `src/modules/kommo/kommo-crypto.service.ts`, `kommo-crypto.service.spec.ts`

**Interfaces:**
- Produces: `KommoCryptoService` com
  - `generateTenantToken(): string` (43 chars base64url)
  - `hashTenantToken(token: string): string` (sha256 hex)
  - `encrypt(plain: string): string` (`v1:<iv>:<tag>:<cipher>`, base64)
  - `decrypt(payload: string): string`
- Config: `app.kommoEncryptionKey: string`, `app.kommoWorkerEnabled: boolean`, `app.kommoWorkerBatchSize: number`.

- [ ] **Step 1: Teste que falha**

```ts
import { randomBytes } from 'node:crypto';
import { KommoCryptoService } from './kommo-crypto.service';

function make(key = randomBytes(32).toString('base64')) {
  const config = { get: vi.fn().mockReturnValue(key) } as any;
  return new KommoCryptoService(config);
}

describe('KommoCryptoService', () => {
  it('criptografa e descriptografa', () => {
    const svc = make();
    const enc = svc.encrypt('long-lived-token');
    expect(enc).not.toContain('long-lived-token');
    expect(svc.decrypt(enc)).toBe('long-lived-token');
  });

  it('cada encrypt usa IV novo', () => {
    const svc = make();
    expect(svc.encrypt('x')).not.toBe(svc.encrypt('x'));
  });

  it('falha com chave diferente', () => {
    const enc = make().encrypt('x');
    expect(() => make().decrypt(enc)).toThrow();
  });

  it('tenant token tem formato fixo e hash determinístico', () => {
    const svc = make();
    const token = svc.generateTenantToken();
    expect(token).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(svc.hashTenantToken(token)).toBe(svc.hashTenantToken(token));
    expect(svc.hashTenantToken(token)).toMatch(/^[0-9a-f]{64}$/);
  });

  it('recusa chave com tamanho errado', () => {
    expect(() => make(Buffer.from('curta').toString('base64'))).toThrow(
      'KOMMO_ENCRYPTION_KEY',
    );
  });
});
```

- [ ] **Step 2:** Run `npx vitest run src/modules/kommo/kommo-crypto.service.spec.ts` → FAIL.

- [ ] **Step 3: Implementar**

Em `app.config.ts`, adicionar na interface `AppConfig`:

```ts
  kommoEncryptionKey: string;
  kommoWorkerEnabled: boolean;
  kommoWorkerBatchSize: number;
```

e no objeto `app`:

```ts
      kommoEncryptionKey: process.env.KOMMO_ENCRYPTION_KEY || '',
      kommoWorkerEnabled: process.env.KOMMO_WORKER_ENABLED !== 'false',
      kommoWorkerBatchSize: parseInt(process.env.KOMMO_WORKER_BATCH_SIZE || '10', 10),
```

`kommo-crypto.service.ts`:

```ts
import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createCipheriv, createDecipheriv, createHash, randomBytes } from 'node:crypto';

const ALGO = 'aes-256-gcm';

@Injectable()
export class KommoCryptoService {
  private readonly key: Buffer;

  constructor(config: ConfigService) {
    this.key = Buffer.from(config.get<string>('app.kommoEncryptionKey') || '', 'base64');
    if (this.key.length !== 32) {
      throw new Error('KOMMO_ENCRYPTION_KEY deve ter 32 bytes em base64');
    }
  }

  generateTenantToken(): string {
    return randomBytes(32).toString('base64url');
  }

  hashTenantToken(token: string): string {
    return createHash('sha256').update(token).digest('hex');
  }

  encrypt(plain: string): string {
    const iv = randomBytes(12);
    const cipher = createCipheriv(ALGO, this.key, iv);
    const data = Buffer.concat([cipher.update(plain, 'utf8'), cipher.final()]);
    return ['v1', iv, cipher.getAuthTag(), data].map((p) =>
      typeof p === 'string' ? p : p.toString('base64'),
    ).join(':');
  }

  decrypt(payload: string): string {
    const [, iv, tag, data] = payload.split(':');
    const decipher = createDecipheriv(ALGO, this.key, Buffer.from(iv, 'base64'));
    decipher.setAuthTag(Buffer.from(tag, 'base64'));
    return Buffer.concat([
      decipher.update(Buffer.from(data, 'base64')),
      decipher.final(),
    ]).toString('utf8');
  }
}
```

- [ ] **Step 4:** Run o mesmo comando → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/config/app.config.ts src/modules/kommo/kommo-crypto.service.ts src/modules/kommo/kommo-crypto.service.spec.ts
git commit -m "feat(kommo): criptografar token do Kommo e gerar tenant token"
```

---

### Task 4: Entidades e repositórios

**Files:**
- Create: `src/modules/kommo/entities/kommo-integration.entity.ts`, `kommo-event.entity.ts`
- Create: `src/modules/kommo/repositories/kommo-integration.repository.ts`, `kommo-event.repository.ts`
- Modify: `src/modules/customers/entities/customer.entity.ts`, `src/modules/customers/repositories/customer.repository.ts`
- Modify: `src/modules/appointments/entities/appointment.entity.ts`, `src/modules/appointments/repositories/appointment.repository.ts`

Repositórios são wrappers finos sobre PostgREST; o projeto não tem testes de repositório. O comportamento é coberto pelos testes de serviço (mocks) e pela validação SQL da Task 1. Verificação desta task: `tsc` + suíte existente.

**Interfaces (Produces):**
- `KommoIntegration`, `KommoEvent`, `KommoEventStatus` (abaixo).
- `KommoIntegrationRepository`: `findActiveByTokenHash(hash)`, `findById(id)`, `findActiveByCompany(companyId)`, `create(data)`, `update(id, data)`.
- `KommoEventRepository`: `enqueue(rows)`, `claim(limit, leaseSeconds)`, `markDone(id, appointmentId)`, `markFailed(id, message)`, `scheduleRetry(id, message, nextAttemptAt: Date)`.
- `CustomerRepository`: nada novo (Task 0B).
- `AppointmentRepository.upsertFromKommo(input: KommoAppointmentInput): Promise<Appointment>`.

- [ ] **Step 1: Entidades**

`kommo-integration.entity.ts`:

```ts
export class KommoIntegration {
  id: string;
  company_id: string;
  company_unit_id: string;
  service_user_id: string;
  subdomain: string;
  access_token_encrypted: string;
  tenant_token_hash: string;
  pipeline_id: number;
  scheduled_status_id: number;
  date_field_id: number;
  time_field_id: number;
  referral_field_id: number | null;
  phone_field_id: number;
  timezone: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;

  constructor(partial: Partial<KommoIntegration>) {
    Object.assign(this, partial);
  }
}
```

`kommo-event.entity.ts`:

```ts
export enum KommoEventStatus {
  PENDING = 'pending',
  PROCESSING = 'processing',
  DONE = 'done',
  FAILED = 'failed',
}

export class KommoEvent {
  id: string;
  integration_id: string;
  company_id: string;
  kommo_lead_id: number;
  payload: unknown;
  status: KommoEventStatus;
  attempts: number;
  next_attempt_at: string;
  locked_until: string | null;
  last_error: string | null;
  appointment_id: string | null;
  created_at: string;
  processed_at: string | null;

  constructor(partial: Partial<KommoEvent>) {
    Object.assign(this, partial);
  }
}
```

- [ ] **Step 2: Repositório de integração**

```ts
import { Injectable } from '@nestjs/common';
import { SupabaseService } from '@/core/database/supabase.service';
import { KommoIntegration } from '../entities/kommo-integration.entity';

const TABLE = 'kommo_integrations';

@Injectable()
export class KommoIntegrationRepository {
  constructor(private readonly supabase: SupabaseService) {}

  private get db(): any {
    return this.supabase.getClient();
  }

  async findActiveByTokenHash(hash: string): Promise<KommoIntegration | null> {
    const { data, error } = await this.db
      .from(TABLE)
      .select('*')
      .eq('tenant_token_hash', hash)
      .is('deleted_at', null)
      .maybeSingle();
    if (error) throw error;
    return data ? new KommoIntegration(data) : null;
  }

  async findById(id: string): Promise<KommoIntegration | null> {
    const { data, error } = await this.db.from(TABLE).select('*').eq('id', id).maybeSingle();
    if (error) throw error;
    return data ? new KommoIntegration(data) : null;
  }

  async findActiveByCompany(companyId: string): Promise<KommoIntegration | null> {
    const { data, error } = await this.db
      .from(TABLE)
      .select('*')
      .eq('company_id', companyId)
      .is('deleted_at', null)
      .maybeSingle();
    if (error) throw error;
    return data ? new KommoIntegration(data) : null;
  }

  async create(data: Partial<KommoIntegration>): Promise<KommoIntegration> {
    const { data: rows, error } = await this.db.from(TABLE).insert(data).select();
    if (error) throw error;
    return new KommoIntegration(rows[0]);
  }

  async update(id: string, data: Partial<KommoIntegration>): Promise<KommoIntegration> {
    const { data: rows, error } = await this.db
      .from(TABLE)
      .update({ ...data, updated_at: new Date().toISOString() })
      .eq('id', id)
      .select();
    if (error) throw error;
    return new KommoIntegration(rows[0]);
  }
}
```

- [ ] **Step 3: Repositório de eventos**

```ts
import { Injectable } from '@nestjs/common';
import { SupabaseService } from '@/core/database/supabase.service';
import { KommoEvent, KommoEventStatus } from '../entities/kommo-event.entity';

const TABLE = 'kommo_events';
const MAX_ERROR_LENGTH = 2000;

@Injectable()
export class KommoEventRepository {
  constructor(private readonly supabase: SupabaseService) {}

  private get db(): any {
    return this.supabase.getClient();
  }

  async enqueue(
    rows: Pick<KommoEvent, 'integration_id' | 'company_id' | 'kommo_lead_id' | 'payload'>[],
  ): Promise<void> {
    const { error } = await this.db.from(TABLE).insert(rows);
    if (error) throw error;
  }

  async claim(limit: number, leaseSeconds: number): Promise<KommoEvent[]> {
    const { data, error } = await this.db.rpc('claim_kommo_events', {
      p_limit: limit,
      p_lease_seconds: leaseSeconds,
    });
    if (error) throw error;
    return (data || []).map((row: any) => new KommoEvent(row));
  }

  async markDone(id: string, appointmentId: string | null): Promise<void> {
    await this.patch(id, {
      status: KommoEventStatus.DONE,
      appointment_id: appointmentId,
      locked_until: null,
      last_error: null,
      processed_at: new Date().toISOString(),
    });
  }

  async markFailed(id: string, message: string): Promise<void> {
    await this.patch(id, {
      status: KommoEventStatus.FAILED,
      locked_until: null,
      last_error: message.slice(0, MAX_ERROR_LENGTH),
      processed_at: new Date().toISOString(),
    });
  }

  async scheduleRetry(id: string, message: string, nextAttemptAt: Date): Promise<void> {
    await this.patch(id, {
      status: KommoEventStatus.PENDING,
      locked_until: null,
      last_error: message.slice(0, MAX_ERROR_LENGTH),
      next_attempt_at: nextAttemptAt.toISOString(),
    });
  }

  private async patch(id: string, data: Partial<KommoEvent>): Promise<void> {
    const { error } = await this.db.from(TABLE).update(data).eq('id', id);
    if (error) throw error;
  }
}
```

- [ ] **Step 4: Cliente** — entidade e repositório já foram ajustados na Task 0B (`matchByPhone`, `findByKommoContactId`, `linkKommoContact`). Agora que a `0010` criou a coluna, em `customer.repository.ts` o `create` pode enviar `kommo_contact_id` sempre (remover o filtro de `null` adicionado na Task 0B só se ele atrapalhar; mantê-lo é inofensivo).

- [ ] **Step 5: Agendamento — entidade e repositório**

Em `appointment.entity.ts`, trocar `lead_phone: string;` por `lead_phone: string | null;` e adicionar:

```ts
  kommo_lead_id: number | null;
  needs_review: boolean;
  review_reason: string | null;
  scheduled_time_unknown: boolean;
```

Em `appointment.repository.ts`, adicionar a interface exportada e o método:

```ts
export interface KommoAppointmentInput {
  companyId: string;
  companyUnitId: string;
  userId: string;
  kommoLeadId: number;
  customerId: string | null;
  leadFullName: string;
  leadPhone: string | null;
  scheduledAt: string;
  scheduledTimeUnknown: boolean;
  notes: string | null;
  needsReview: boolean;
  reviewReason: string | null;
}
```

```ts
  async upsertFromKommo(input: KommoAppointmentInput): Promise<Appointment> {
    const { data, error } = await this.db.rpc('upsert_kommo_appointment', {
      p_company_id: input.companyId,
      p_company_unit_id: input.companyUnitId,
      p_user_id: input.userId,
      p_kommo_lead_id: input.kommoLeadId,
      p_customer_id: input.customerId,
      p_lead_full_name: input.leadFullName,
      p_lead_phone: input.leadPhone,
      p_scheduled_at: input.scheduledAt,
      p_scheduled_time_unknown: input.scheduledTimeUnknown,
      p_notes: input.notes,
      p_needs_review: input.needsReview,
      p_review_reason: input.reviewReason,
    });
    if (error) throw error;
    const rows = Array.isArray(data) ? data : [data];
    return new Appointment(rows[0]);
  }
```

- [ ] **Step 5B: Expor os campos na resposta** — em `src/modules/appointments/dto/appointment.dto.ts`, `AppointmentResponseDto`: `lead_phone` vira `@ApiProperty({ nullable: true }) lead_phone: string | null;` e adicionar:

```ts
  @ApiProperty({ description: 'true = exibir "horário a confirmar" em vez da hora de scheduled_at' })
  scheduled_time_unknown: boolean;

  @ApiProperty()
  needs_review: boolean;

  @ApiProperty({ nullable: true })
  review_reason: string | null;

  @ApiProperty({ nullable: true })
  kommo_lead_id: number | null;
```

Os controllers devolvem a entidade inteira, então os campos já saem na listagem; o DTO documenta o contrato no Swagger para a interface.

- [ ] **Step 6: Verificar**

Run: `npx tsc --noEmit && npx vitest run`
Expected: sem erros de tipo; specs existentes passam. Se algum spec quebrar só pelo tipo de `phone`/`lead_phone` agora aceitar `null`, ajustar o tipo no spec, não a regra.

- [ ] **Step 7: Commit**

```bash
git add src/modules/kommo/entities src/modules/kommo/repositories src/modules/customers src/modules/appointments
git commit -m "feat(kommo): repositórios de integração, outbox e upsert de cliente/agendamento"
```

---

### Task 5: Endpoint de ingestão

**Files:**
- Create: `src/modules/kommo/kommo-webhook.service.ts`, `kommo-webhook.service.spec.ts`
- Create: `src/modules/kommo/kommo-webhook.controller.ts`
- Create: `src/modules/kommo/kommo.module.ts`
- Modify: `src/main.ts`, `src/app.module.ts`

**Interfaces:**
- Consumes: `KommoCryptoService.hashTenantToken`, `KommoIntegrationRepository.findActiveByTokenHash`, `KommoEventRepository.enqueue`, `extractLeadIds`.
- Produces: `KommoWebhookService.ingest(tenantToken: string, body: unknown): Promise<{ queued: number }>`; lança `UnauthorizedException` para token inválido.

- [ ] **Step 1: Teste que falha**

```ts
import { UnauthorizedException } from '@nestjs/common';
import { KommoIntegration } from './entities/kommo-integration.entity';
import { KommoWebhookService } from './kommo-webhook.service';

const VALID_TOKEN = 'a'.repeat(43);

describe('KommoWebhookService', () => {
  const integration = new KommoIntegration({
    id: 'int-1',
    company_id: 'comp-1',
    scheduled_status_id: 112039795,
  });
  let crypto: any;
  let integrations: any;
  let events: any;
  let service: KommoWebhookService;

  beforeEach(() => {
    crypto = { hashTenantToken: vi.fn().mockReturnValue('hash') };
    integrations = { findActiveByTokenHash: vi.fn().mockResolvedValue(integration) };
    events = { enqueue: vi.fn().mockResolvedValue(undefined) };
    service = new KommoWebhookService(crypto, integrations, events);
  });

  it('enfileira um evento por lead com o payload bruto', async () => {
    const body = { lead_id: '42' };
    await expect(service.ingest(VALID_TOKEN, body)).resolves.toEqual({ queued: 1 });
    expect(integrations.findActiveByTokenHash).toHaveBeenCalledWith('hash');
    expect(events.enqueue).toHaveBeenCalledWith([
      { integration_id: 'int-1', company_id: 'comp-1', kommo_lead_id: 42, payload: body },
    ]);
  });

  it('ignora leads de outra etapa sem gravar', async () => {
    const body = { leads: { status: [{ id: '1', status_id: '5' }] } };
    await expect(service.ingest(VALID_TOKEN, body)).resolves.toEqual({ queued: 0 });
    expect(events.enqueue).not.toHaveBeenCalled();
  });

  it('token desconhecido → 401 sem enfileirar', async () => {
    integrations.findActiveByTokenHash.mockResolvedValue(null);
    await expect(service.ingest(VALID_TOKEN, { lead_id: 1 })).rejects.toBeInstanceOf(
      UnauthorizedException,
    );
    expect(events.enqueue).not.toHaveBeenCalled();
  });

  it.each(['curto', 'x'.repeat(500), 'tem espaço aqui no meio do token'])(
    'token com formato inválido (%s) nem consulta o banco',
    async (token) => {
      await expect(service.ingest(token, {})).rejects.toBeInstanceOf(UnauthorizedException);
      expect(integrations.findActiveByTokenHash).not.toHaveBeenCalled();
    },
  );
});
```

- [ ] **Step 2:** Run `npx vitest run src/modules/kommo/kommo-webhook.service.spec.ts` → FAIL.

- [ ] **Step 3: Implementar**

`kommo-webhook.service.ts`:

```ts
import { Injectable, Logger, UnauthorizedException } from '@nestjs/common';
import { KommoCryptoService } from './kommo-crypto.service';
import { KommoEventRepository } from './repositories/kommo-event.repository';
import { KommoIntegrationRepository } from './repositories/kommo-integration.repository';
import { extractLeadIds } from './utils/kommo-payload.util';

const TOKEN_RE = /^[A-Za-z0-9_-]{20,100}$/;

@Injectable()
export class KommoWebhookService {
  private readonly logger = new Logger(KommoWebhookService.name);

  constructor(
    private readonly crypto: KommoCryptoService,
    private readonly integrations: KommoIntegrationRepository,
    private readonly events: KommoEventRepository,
  ) {}

  async ingest(tenantToken: string, body: unknown): Promise<{ queued: number }> {
    if (!TOKEN_RE.test(tenantToken)) {
      throw new UnauthorizedException('Token de integração inválido');
    }
    const integration = await this.integrations.findActiveByTokenHash(
      this.crypto.hashTenantToken(tenantToken),
    );
    if (!integration) {
      throw new UnauthorizedException('Token de integração inválido');
    }

    const leadIds = extractLeadIds(body, Number(integration.scheduled_status_id));
    if (leadIds.length === 0) {
      this.logger.log(`Webhook sem lead elegível (integração ${integration.id})`);
      return { queued: 0 };
    }

    await this.events.enqueue(
      leadIds.map((kommo_lead_id) => ({
        integration_id: integration.id,
        company_id: integration.company_id,
        kommo_lead_id,
        payload: body,
      })),
    );
    return { queued: leadIds.length };
  }
}
```

`kommo-webhook.controller.ts` — `@Body() body: unknown` faz o `ValidationPipe` global (com `forbidNonWhitelisted`) ignorar o corpo, que é livre:

```ts
import { Body, Controller, HttpCode, Param, Post } from '@nestjs/common';
import { ApiExcludeController } from '@nestjs/swagger';
import { Throttle } from '@nestjs/throttler';
import { KommoWebhookService } from './kommo-webhook.service';

@ApiExcludeController()
@Controller('kommo')
export class KommoWebhookController {
  constructor(private readonly service: KommoWebhookService) {}

  // Kommo dispara de poucos IPs compartilhados entre todas as contas.
  @Throttle({ default: { limit: 1000, ttl: 60000 } })
  @Post('agendamento/:tenantToken')
  @HttpCode(200)
  async receive(@Param('tenantToken') tenantToken: string, @Body() body: unknown) {
    const { queued } = await this.service.ingest(tenantToken, body);
    return { ok: true, queued };
  }
}
```

`kommo.module.ts` (versão inicial; Tasks 7–9 acrescentam providers):

```ts
import { Module } from '@nestjs/common';
import { KommoCryptoService } from './kommo-crypto.service';
import { KommoWebhookController } from './kommo-webhook.controller';
import { KommoWebhookService } from './kommo-webhook.service';
import { KommoEventRepository } from './repositories/kommo-event.repository';
import { KommoIntegrationRepository } from './repositories/kommo-integration.repository';

@Module({
  controllers: [KommoWebhookController],
  providers: [
    KommoCryptoService,
    KommoWebhookService,
    KommoIntegrationRepository,
    KommoEventRepository,
  ],
})
export class KommoModule {}
```

`app.module.ts`: importar `KommoModule` e adicioná-lo em `imports` logo depois de `AppointmentsModule`.

`main.ts`: adicionar `import { NestExpressApplication } from '@nestjs/platform-express';` e trocar a criação do app por:

```ts
  const app = await NestFactory.create<NestExpressApplication>(AppModule);
  // Kommo envia form-urlencoded com chaves aninhadas (leads[status][0][id]); Express 5 não aninha por padrão.
  app.useBodyParser('urlencoded', { extended: true, limit: '1mb' });
```

- [ ] **Step 4: Rodar testes e smoke test manual**

Run: `npx vitest run src/modules/kommo`
Expected: PASS.

Com a API rodando (`npm run start:dev`), `KOMMO_ENCRYPTION_KEY` definido e uma integração de teste inserida (hash de um `$TOKEN` conhecido):

```bash
curl -s -w ' %{http_code} %{time_total}s\n' -X POST "http://localhost:8000/kommo/agendamento/$TOKEN" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data 'leads[status][0][id]=123&leads[status][0][status_id]=112039795&leads[status][0][pipeline_id]=14505231'
curl -s -w ' %{http_code}\n' -X POST "http://localhost:8000/kommo/agendamento/$TOKEN" \
  -H 'Content-Type: application/json' -d '{"lead_id":123}'
curl -s -w ' %{http_code}\n' -X POST "http://localhost:8000/kommo/agendamento/tokeninvalidoxxxxxxxxxxxxxx" -d 'lead_id=1'
```

Expected: `200` / `200` / `401`; tempo bem abaixo de 2s; duas linhas novas em `kommo_events`. Conferir que a resposta passa pelo `ResponseTransformInterceptor` sem erro.

- [ ] **Step 5: Commit**

```bash
git add src/main.ts src/app.module.ts src/modules/kommo
git commit -m "feat(kommo): endpoint de webhook que grava eventos no outbox"
```

---

### Task 6: Cliente da API v4 do Kommo

**Files:**
- Create: `src/modules/kommo/kommo-client.ts`, `kommo-client.spec.ts`

**Interfaces:**
- Produces: `KommoApiError` (`status: number`, `retryable: boolean`; status 0 = rede), `KommoLead`, `KommoContact`, `KommoCustomField`, `fieldValue(fields, fieldId): unknown`, `KommoClient(subdomain, accessToken, fetchFn?)` com `getLead(id)`, `getContact(id)`, `addLeadNote(leadId, text)`. 401/403/404 → não retentável; 429/5xx/rede → retentável.

- [ ] **Step 1: Teste que falha**

```ts
import { KommoApiError, KommoClient, fieldValue } from './kommo-client';

function res(status: number, body: unknown = {}) {
  return new Response(JSON.stringify(body), { status });
}

describe('KommoClient', () => {
  it('busca lead com contatos usando bearer e subdomínio', async () => {
    const fetchFn = vi.fn().mockResolvedValue(res(200, { id: 7, name: 'Lead' }));
    const client = new KommoClient('zyros', 'tok', fetchFn);
    await expect(client.getLead(7)).resolves.toMatchObject({ id: 7 });
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe('https://zyros.kommo.com/api/v4/leads/7?with=contacts');
    expect(init.headers.Authorization).toBe('Bearer tok');
  });

  it('cria nota comum no lead', async () => {
    const fetchFn = vi.fn().mockResolvedValue(res(200, {}));
    await new KommoClient('zyros', 'tok', fetchFn).addLeadNote(7, 'oi');
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe('https://zyros.kommo.com/api/v4/leads/7/notes');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual([{ note_type: 'common', params: { text: 'oi' } }]);
  });

  it.each([
    [401, false],
    [403, false],
    [404, false],
    [429, true],
    [500, true],
  ])('status %i → retryable %s', async (status, retryable) => {
    const fetchFn = vi.fn().mockResolvedValue(res(status));
    const err = await new KommoClient('z', 't', fetchFn).getLead(1).catch((e) => e);
    expect(err).toBeInstanceOf(KommoApiError);
    expect(err.status).toBe(status);
    expect(err.retryable).toBe(retryable);
  });

  it('erro de rede é retentável', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new TypeError('fetch failed'));
    const err = await new KommoClient('z', 't', fetchFn).getLead(1).catch((e) => e);
    expect(err).toMatchObject({ retryable: true, status: 0 });
  });
});

describe('fieldValue', () => {
  const fields = [{ field_id: 614093, values: [{ value: '14:30' }] }];
  it('acha pelo id', () => expect(fieldValue(fields, 614093)).toBe('14:30'));
  it('ausente → null', () => expect(fieldValue(fields, 1)).toBeNull());
  it('lista nula → null', () => expect(fieldValue(null, 1)).toBeNull());
  it('fieldId nulo → null', () => expect(fieldValue(fields, null)).toBeNull());
});
```

- [ ] **Step 2:** Run `npx vitest run src/modules/kommo/kommo-client.spec.ts` → FAIL.

- [ ] **Step 3: Implementar**

```ts
export class KommoApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryable: boolean,
  ) {
    super(message);
  }
}

export interface KommoCustomField {
  field_id: number;
  values: { value: unknown }[];
}

export interface KommoLead {
  id: number;
  name: string;
  status_id: number;
  pipeline_id: number;
  custom_fields_values: KommoCustomField[] | null;
  _embedded?: { contacts?: { id: number; is_main: boolean }[] };
}

export interface KommoContact {
  id: number;
  name: string;
  custom_fields_values: KommoCustomField[] | null;
}

export function fieldValue(
  fields: KommoCustomField[] | null | undefined,
  fieldId: number | null,
): unknown {
  if (!fields || fieldId === null) return null;
  const field = fields.find((f) => Number(f.field_id) === Number(fieldId));
  return field?.values?.[0]?.value ?? null;
}

const TIMEOUT_MS = 10_000;

export class KommoClient {
  private readonly baseUrl: string;

  constructor(
    subdomain: string,
    private readonly accessToken: string,
    private readonly fetchFn: typeof fetch = fetch,
  ) {
    this.baseUrl = `https://${subdomain}.kommo.com/api/v4`;
  }

  getLead(id: number): Promise<KommoLead> {
    return this.request(`/leads/${id}?with=contacts`);
  }

  getContact(id: number): Promise<KommoContact> {
    return this.request(`/contacts/${id}`);
  }

  async addLeadNote(leadId: number, text: string): Promise<void> {
    await this.request(`/leads/${leadId}/notes`, {
      method: 'POST',
      body: JSON.stringify([{ note_type: 'common', params: { text } }]),
    });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    let response: Response;
    try {
      response = await this.fetchFn(`${this.baseUrl}${path}`, {
        ...init,
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(TIMEOUT_MS),
      });
    } catch (err) {
      throw new KommoApiError(`Falha de rede no Kommo: ${(err as Error).message}`, 0, true);
    }

    if (!response.ok) {
      const retryable = response.status === 429 || response.status >= 500;
      throw new KommoApiError(`Kommo respondeu ${response.status} em ${path}`, response.status, retryable);
    }
    return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
  }
}
```

- [ ] **Step 4:** Run o mesmo comando → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/modules/kommo/kommo-client.ts src/modules/kommo/kommo-client.spec.ts
git commit -m "feat(kommo): cliente da API v4 para lead, contato e nota"
```

---

### Task 7: Processador de evento

**Files:**
- Create: `src/modules/kommo/kommo-event-processor.service.ts`, `kommo-event-processor.service.spec.ts`
- Modify: `src/modules/kommo/kommo.module.ts`

**Interfaces:**
- Consumes: `KommoIntegrationRepository.findById`, `KommoCryptoService.decrypt`, `KommoClient`, `fieldValue`, `parseSchedule`, `normalizePhone`, `CustomerMatchingService.resolve` (Task 0B), `AppointmentRepository.upsertFromKommo`, `formatTitleCase` (`@/common/utils/text.util`).
- Produces: `KommoPermanentError`, `KommoClientFactory`, `KOMMO_CLIENT_FACTORY`, `KommoEventProcessorService.process(event: KommoEvent): Promise<string>` (id do agendamento). Erro permanente → `KommoPermanentError`; erros do Kommo propagam como `KommoApiError` para o worker decidir.

Regras, em ordem:
1. Integração ausente ou deletada → `KommoPermanentError('Integração desativada')`.
2. `getLead`. Contato principal = `is_main`, senão o primeiro; sem contato → segue só com o nome do lead e sem telefone.
3. `parseSchedule`; `ok:false` → nota no lead com o motivo e `KommoPermanentError(reason)`.
4. Telefone do contato via `phone_field_id` → `normalizePhone`. Nome = `formatTitleCase(contact.name || lead.name)`; vazio → `'Sem Nome'` + revisão.
5. Cliente: `CustomerMatchingService.resolve({ ..., kommoContactId: contact?.id ?? null })`. Se devolver `reviewReason` (possível duplicado), ele entra nos motivos de revisão do agendamento.
6. Motivos de revisão em `review_reason`, separados por `; `.
7. `notes` = `Indicação: <valor>` ou `null`.
8. `upsertFromKommo`, depois nota de sucesso. Falha na nota só é logada (agendamento já gravado; não reprocessar).

- [ ] **Step 1: Teste que falha**

```ts
import { KommoApiError } from './kommo-client';
import { KommoEvent } from './entities/kommo-event.entity';
import { KommoIntegration } from './entities/kommo-integration.entity';
import {
  KommoEventProcessorService,
  KommoPermanentError,
} from './kommo-event-processor.service';

const LOCAL_MIDNIGHT = Date.UTC(2026, 9, 20, 3) / 1000;

describe('KommoEventProcessorService', () => {
  const integration = new KommoIntegration({
    id: 'int-1',
    company_id: 'comp-1',
    company_unit_id: 'unit-1',
    service_user_id: 'svc-1',
    subdomain: 'zyros',
    access_token_encrypted: 'enc',
    date_field_id: 614091,
    time_field_id: 614093,
    referral_field_id: 566124,
    phone_field_id: 268220,
    timezone: 'America/Araguaina',
    deleted_at: null,
  });
  const event = new KommoEvent({ id: 'ev-1', integration_id: 'int-1', kommo_lead_id: 55 });

  let integrations: any;
  let crypto: any;
  let client: any;
  let customers: any;
  let appointments: any;
  let service: KommoEventProcessorService;

  function lead(time: unknown = '14:30', date: unknown = LOCAL_MIDNIGHT) {
    return {
      id: 55,
      name: 'Lead 55',
      custom_fields_values: [
        { field_id: 614091, values: [{ value: date }] },
        { field_id: 614093, values: [{ value: time }] },
        { field_id: 566124, values: [{ value: 'Dra. Ana' }] },
      ],
      _embedded: { contacts: [{ id: 900, is_main: true }] },
    };
  }

  beforeEach(() => {
    integrations = { findById: vi.fn().mockResolvedValue(integration) };
    crypto = { decrypt: vi.fn().mockReturnValue('kommo-token') };
    client = {
      getLead: vi.fn().mockResolvedValue(lead()),
      getContact: vi.fn().mockResolvedValue({
        id: 900,
        name: 'MARIA DA SILVA',
        custom_fields_values: [{ field_id: 268220, values: [{ value: '+55 63 99123-4567' }] }],
      }),
      addLeadNote: vi.fn().mockResolvedValue(undefined),
    };
    customers = {
      resolve: vi.fn().mockResolvedValue({ customerId: 'cust-new', created: true, reviewReason: null }),
    };
    appointments = { upsertFromKommo: vi.fn().mockResolvedValue({ id: 'appt-1' }) };
    service = new KommoEventProcessorService(
      integrations,
      crypto,
      customers,
      appointments,
      () => client,
    );
  });

  it('caminho feliz: resolve cliente, faz upsert e escreve nota', async () => {
    await expect(service.process(event)).resolves.toBe('appt-1');
    expect(customers.resolve).toHaveBeenCalledWith({
      companyId: 'comp-1',
      companyUnitId: 'unit-1',
      userId: 'svc-1',
      fullName: 'Maria da Silva',
      phone: '63991234567',
      kommoContactId: 900,
    });
    expect(appointments.upsertFromKommo).toHaveBeenCalledWith({
      companyId: 'comp-1',
      companyUnitId: 'unit-1',
      userId: 'svc-1',
      kommoLeadId: 55,
      customerId: 'cust-new',
      leadFullName: 'Maria da Silva',
      leadPhone: '63991234567',
      scheduledAt: '2026-10-20T14:30:00-03:00',
      scheduledTimeUnknown: false,
      notes: 'Indicação: Dra. Ana',
      needsReview: false,
      reviewReason: null,
    });
    expect(client.addLeadNote).toHaveBeenCalledWith(
      55,
      'Agendamento registrado no OticaLab para 20/10/2026 às 14:30.',
    );
  });

  it('possível duplicado vira motivo de revisão do agendamento', async () => {
    customers.resolve.mockResolvedValue({
      customerId: 'cust-new',
      created: true,
      reviewReason: 'Possível duplicado de cust-x',
    });
    await service.process(event);
    expect(appointments.upsertFromKommo).toHaveBeenCalledWith(
      expect.objectContaining({ needsReview: true, reviewReason: 'Possível duplicado de cust-x' }),
    );
  });

  it('horário inválido grava 00:00 com revisão', async () => {
    client.getLead.mockResolvedValue(lead('manhã'));
    await service.process(event);
    expect(appointments.upsertFromKommo).toHaveBeenCalledWith(
      expect.objectContaining({
        scheduledAt: '2026-10-20T00:00:00-03:00',
        scheduledTimeUnknown: true,
        needsReview: true,
        reviewReason: 'Horário vazio ou inválido',
      }),
    );
    expect(client.addLeadNote).toHaveBeenCalledWith(
      55,
      'Agendamento registrado no OticaLab para 20/10/2026 (horário a confirmar).\nRevisar: Horário vazio ou inválido',
    );
  });

  it('telefone inválido segue com phone null e revisão', async () => {
    client.getContact.mockResolvedValue({
      id: 900,
      name: 'Maria',
      custom_fields_values: [{ field_id: 268220, values: [{ value: '123' }] }],
    });
    await service.process(event);
    expect(customers.resolve).toHaveBeenCalledWith(expect.objectContaining({ phone: null }));
    expect(appointments.upsertFromKommo).toHaveBeenCalledWith(
      expect.objectContaining({ leadPhone: null, reviewReason: 'Telefone inválido ou ausente' }),
    );
  });

  it('lead sem contato usa o nome do lead', async () => {
    client.getLead.mockResolvedValue({ ...lead(), _embedded: { contacts: [] } });
    await service.process(event);
    expect(client.getContact).not.toHaveBeenCalled();
    expect(customers.resolve).toHaveBeenCalledWith(
      expect.objectContaining({ fullName: 'Lead 55', phone: null, kommoContactId: null }),
    );
    expect(appointments.upsertFromKommo).toHaveBeenCalledWith(
      expect.objectContaining({ leadFullName: 'Lead 55', leadPhone: null }),
    );
  });

  it('data inválida → nota explicando e erro permanente', async () => {
    client.getLead.mockResolvedValue(lead('10:00', null));
    await expect(service.process(event)).rejects.toBeInstanceOf(KommoPermanentError);
    expect(appointments.upsertFromKommo).not.toHaveBeenCalled();
    expect(client.addLeadNote).toHaveBeenCalledWith(
      55,
      'Não foi possível registrar o agendamento no OticaLab: Data do agendamento vazia ou inválida.',
    );
  });

  it('falha ao escrever nota não derruba o processamento', async () => {
    client.addLeadNote.mockRejectedValue(new KommoApiError('x', 500, true));
    await expect(service.process(event)).resolves.toBe('appt-1');
  });

  it('integração removida → erro permanente', async () => {
    integrations.findById.mockResolvedValue(new KommoIntegration({ deleted_at: '2026-01-01' }));
    await expect(service.process(event)).rejects.toBeInstanceOf(KommoPermanentError);
  });

  it('erro do Kommo ao buscar lead propaga para o worker decidir retry', async () => {
    client.getLead.mockRejectedValue(new KommoApiError('x', 503, true));
    await expect(service.process(event)).rejects.toMatchObject({ retryable: true });
  });
});
```

- [ ] **Step 2:** Run `npx vitest run src/modules/kommo/kommo-event-processor.service.spec.ts` → FAIL.

- [ ] **Step 3: Implementar**

```ts
import { Inject, Injectable, Logger } from '@nestjs/common';
import { formatTitleCase } from '@/common/utils/text.util';
import { AppointmentRepository } from '@/modules/appointments/repositories/appointment.repository';
import { CustomerMatchingService } from '@/modules/customers/customer-matching.service';
import { KommoEvent } from './entities/kommo-event.entity';
import { KommoClient, fieldValue } from './kommo-client';
import { KommoCryptoService } from './kommo-crypto.service';
import { KommoIntegrationRepository } from './repositories/kommo-integration.repository';
import { normalizePhone } from '@/common/utils/phone.util';
import { parseSchedule } from './utils/kommo-schedule.util';

export class KommoPermanentError extends Error {}

export type KommoClientFactory = (subdomain: string, token: string) => KommoClient;
export const KOMMO_CLIENT_FACTORY = 'KOMMO_CLIENT_FACTORY';

const REVIEW = {
  time: 'Horário vazio ou inválido',
  phone: 'Telefone inválido ou ausente',
  name: 'Lead sem nome',
};

@Injectable()
export class KommoEventProcessorService {
  private readonly logger = new Logger(KommoEventProcessorService.name);

  constructor(
    private readonly integrations: KommoIntegrationRepository,
    private readonly crypto: KommoCryptoService,
    private readonly customers: CustomerMatchingService,
    private readonly appointments: AppointmentRepository,
    @Inject(KOMMO_CLIENT_FACTORY) private readonly clientFactory: KommoClientFactory,
  ) {}

  async process(event: KommoEvent): Promise<string> {
    const integration = await this.integrations.findById(event.integration_id);
    if (!integration || integration.deleted_at) {
      throw new KommoPermanentError('Integração desativada');
    }

    const client = this.clientFactory(
      integration.subdomain,
      this.crypto.decrypt(integration.access_token_encrypted),
    );
    const leadId = Number(event.kommo_lead_id);
    const lead = await client.getLead(leadId);

    const schedule = parseSchedule(
      fieldValue(lead.custom_fields_values, integration.date_field_id),
      fieldValue(lead.custom_fields_values, integration.time_field_id),
      integration.timezone,
    );
    if (!schedule.ok) {
      await this.safeNote(
        client,
        leadId,
        `Não foi possível registrar o agendamento no OticaLab: ${schedule.reason}.`,
      );
      throw new KommoPermanentError(schedule.reason);
    }

    const contacts = lead._embedded?.contacts ?? [];
    const mainContact = contacts.find((c) => c.is_main) ?? contacts[0];
    const contact = mainContact ? await client.getContact(mainContact.id) : null;

    const reasons: string[] = [];
    if (schedule.timeUnknown) reasons.push(REVIEW.time);

    const rawPhone = contact
      ? fieldValue(contact.custom_fields_values, integration.phone_field_id)
      : null;
    const phone = normalizePhone(rawPhone === null ? null : String(rawPhone));
    if (!phone) reasons.push(REVIEW.phone);

    let fullName = formatTitleCase(contact?.name || lead.name);
    if (!fullName) {
      fullName = 'Sem Nome';
      reasons.push(REVIEW.name);
    }

    const resolved = await this.customers.resolve({
      companyId: integration.company_id,
      companyUnitId: integration.company_unit_id,
      userId: integration.service_user_id,
      fullName,
      phone,
      kommoContactId: contact?.id ?? null,
    });
    if (resolved.reviewReason) reasons.push(resolved.reviewReason);

    const referral = fieldValue(lead.custom_fields_values, integration.referral_field_id);
    const appointment = await this.appointments.upsertFromKommo({
      companyId: integration.company_id,
      companyUnitId: integration.company_unit_id,
      userId: integration.service_user_id,
      kommoLeadId: leadId,
      customerId: resolved.customerId,
      leadFullName: fullName,
      leadPhone: phone,
      scheduledAt: schedule.scheduledAt,
      scheduledTimeUnknown: schedule.timeUnknown,
      notes: referral ? `Indicação: ${referral}` : null,
      needsReview: reasons.length > 0,
      reviewReason: reasons.length > 0 ? reasons.join('; ') : null,
    });

    await this.safeNote(
      client,
      leadId,
      this.successNote(schedule.scheduledAt, schedule.timeUnknown, reasons),
    );
    return appointment.id;
  }

  private successNote(scheduledAt: string, timeUnknown: boolean, reasons: string[]): string {
    const [date, time] = scheduledAt.slice(0, 16).split('T');
    const [y, m, d] = date.split('-');
    const when = timeUnknown ? `${d}/${m}/${y} (horário a confirmar)` : `${d}/${m}/${y} às ${time}`;
    const review = reasons.length > 0 ? `\nRevisar: ${reasons.join('; ')}` : '';
    return `Agendamento registrado no OticaLab para ${when}.${review}`;
  }

  private async safeNote(client: KommoClient, leadId: number, text: string): Promise<void> {
    try {
      await client.addLeadNote(leadId, text);
    } catch (err) {
      this.logger.warn(`Falha ao criar nota no lead ${leadId}: ${(err as Error).message}`);
    }
  }
}
```

Em `kommo.module.ts`: adicionar `imports: [CustomersModule, AppointmentsModule]` (exportam `CustomerMatchingService` e `AppointmentRepository`) e, nos providers:

```ts
    KommoEventProcessorService,
    {
      provide: KOMMO_CLIENT_FACTORY,
      useValue: (subdomain: string, token: string) => new KommoClient(subdomain, token),
    },
```

- [ ] **Step 4:** Run o mesmo comando → PASS. Depois `npx tsc --noEmit`.

- [ ] **Step 5: Commit**

```bash
git add src/modules/kommo
git commit -m "feat(kommo): processar evento com upsert de cliente, agendamento e nota no lead"
```

---

### Task 8: Worker (intervalo + retry)

**Files:**
- Create: `src/modules/kommo/kommo-worker.service.ts`, `kommo-worker.service.spec.ts`
- Modify: `package.json` / `package-lock.json` (dep `@nestjs/schedule`), `src/app.module.ts`, `src/modules/kommo/kommo.module.ts`

**Interfaces:**
- Consumes: `KommoEventRepository.{claim, markDone, markFailed, scheduleRetry}`, `KommoEventProcessorService.process`, `KommoPermanentError`, `KommoApiError`.
- Produces: `KommoWorkerService.tick(): Promise<number>`; `MAX_ATTEMPTS = 6`; `LEASE_SECONDS = 120`; `backoffSeconds(attempts) = min(30 * 2^(attempts-1), 3600)`.

Regras: `KommoPermanentError`, `KommoApiError` não retentável ou `attempts >= MAX_ATTEMPTS` → `markFailed`; senão `scheduleRetry(now + backoff)`. Erro num evento não interrompe os demais. A flag `running` só evita reentrância do timer na mesma instância; a coordenação entre réplicas é do `SKIP LOCKED`.

- [ ] **Step 1: Instalar dependência**

```bash
npm install @nestjs/schedule
npm ls @nestjs/schedule
```

Expected: instalado sem conflito de peer com `@nestjs/common` 12. Se houver conflito, parar e avisar o usuário.

- [ ] **Step 2: Teste que falha**

```ts
import { KommoApiError } from './kommo-client';
import { KommoEvent } from './entities/kommo-event.entity';
import { KommoPermanentError } from './kommo-event-processor.service';
import { KommoWorkerService, backoffSeconds } from './kommo-worker.service';

describe('backoffSeconds', () => {
  it.each([
    [1, 30],
    [2, 60],
    [3, 120],
    [20, 3600],
  ])('tentativa %i → %is', (n, s) => expect(backoffSeconds(n)).toBe(s));
});

describe('KommoWorkerService', () => {
  let events: any;
  let processor: any;
  let config: any;
  let worker: KommoWorkerService;
  const ev = (id: string, attempts = 1) => new KommoEvent({ id, attempts });

  beforeEach(() => {
    events = {
      claim: vi.fn().mockResolvedValue([]),
      markDone: vi.fn(),
      markFailed: vi.fn(),
      scheduleRetry: vi.fn(),
    };
    processor = { process: vi.fn() };
    config = { get: vi.fn((k: string) => (k === 'app.kommoWorkerBatchSize' ? 10 : true)) };
    worker = new KommoWorkerService(events, processor, config);
  });

  afterEach(() => vi.useRealTimers());

  it('reivindica com lease e marca sucesso', async () => {
    events.claim.mockResolvedValue([ev('a')]);
    processor.process.mockResolvedValue('appt-1');
    await expect(worker.tick()).resolves.toBe(1);
    expect(events.claim).toHaveBeenCalledWith(10, 120);
    expect(events.markDone).toHaveBeenCalledWith('a', 'appt-1');
  });

  it('erro permanente → failed sem retry', async () => {
    events.claim.mockResolvedValue([ev('a')]);
    processor.process.mockRejectedValue(new KommoPermanentError('Data inválida'));
    await worker.tick();
    expect(events.markFailed).toHaveBeenCalledWith('a', 'Data inválida');
    expect(events.scheduleRetry).not.toHaveBeenCalled();
  });

  it('401 do Kommo → failed sem retry', async () => {
    events.claim.mockResolvedValue([ev('a')]);
    processor.process.mockRejectedValue(new KommoApiError('Kommo respondeu 401', 401, false));
    await worker.tick();
    expect(events.markFailed).toHaveBeenCalledWith('a', 'Kommo respondeu 401');
  });

  it('erro transitório → retry com backoff', async () => {
    vi.useFakeTimers().setSystemTime(new Date('2026-10-14T12:00:00Z'));
    events.claim.mockResolvedValue([ev('a', 2)]);
    processor.process.mockRejectedValue(new KommoApiError('503', 503, true));
    await worker.tick();
    expect(events.scheduleRetry).toHaveBeenCalledWith('a', '503', new Date('2026-10-14T12:01:00Z'));
  });

  it('esgotou tentativas → failed', async () => {
    events.claim.mockResolvedValue([ev('a', 6)]);
    processor.process.mockRejectedValue(new Error('timeout'));
    await worker.tick();
    expect(events.markFailed).toHaveBeenCalledWith('a', 'timeout');
  });

  it('falha em um evento não impede os outros', async () => {
    events.claim.mockResolvedValue([ev('a'), ev('b')]);
    processor.process.mockRejectedValueOnce(new Error('x')).mockResolvedValueOnce('appt-b');
    await expect(worker.tick()).resolves.toBe(2);
    expect(events.markDone).toHaveBeenCalledWith('b', 'appt-b');
  });

  it('desligado por config não reivindica nada', async () => {
    config.get = vi.fn((k: string) => (k === 'app.kommoWorkerEnabled' ? false : 10));
    worker = new KommoWorkerService(events, processor, config);
    await expect(worker.tick()).resolves.toBe(0);
    expect(events.claim).not.toHaveBeenCalled();
  });

  it('tick reentrante na mesma instância é ignorado', async () => {
    let release!: () => void;
    events.claim.mockReturnValue(new Promise((r) => (release = () => r([]))));
    const first = worker.tick();
    await expect(worker.tick()).resolves.toBe(0);
    release();
    await first;
    expect(events.claim).toHaveBeenCalledTimes(1);
  });
});
```

- [ ] **Step 3:** Run `npx vitest run src/modules/kommo/kommo-worker.service.spec.ts` → FAIL.

- [ ] **Step 4: Implementar**

```ts
import { Injectable, Logger } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { Interval } from '@nestjs/schedule';
import { KommoEvent } from './entities/kommo-event.entity';
import { KommoApiError } from './kommo-client';
import { KommoEventProcessorService, KommoPermanentError } from './kommo-event-processor.service';
import { KommoEventRepository } from './repositories/kommo-event.repository';

export const MAX_ATTEMPTS = 6;
export const LEASE_SECONDS = 120;

export function backoffSeconds(attempts: number): number {
  return Math.min(30 * 2 ** (attempts - 1), 3600);
}

@Injectable()
export class KommoWorkerService {
  private readonly logger = new Logger(KommoWorkerService.name);
  private running = false;

  constructor(
    private readonly events: KommoEventRepository,
    private readonly processor: KommoEventProcessorService,
    private readonly config: ConfigService,
  ) {}

  @Interval(5000)
  async tick(): Promise<number> {
    if (this.running || !this.config.get<boolean>('app.kommoWorkerEnabled')) return 0;
    this.running = true;
    try {
      const batch = await this.events.claim(
        this.config.get<number>('app.kommoWorkerBatchSize') || 10,
        LEASE_SECONDS,
      );
      for (const event of batch) {
        await this.handle(event);
      }
      return batch.length;
    } catch (err) {
      this.logger.error(`Falha ao reivindicar eventos Kommo: ${(err as Error).message}`);
      return 0;
    } finally {
      this.running = false;
    }
  }

  private async handle(event: KommoEvent): Promise<void> {
    try {
      const appointmentId = await this.processor.process(event);
      await this.events.markDone(event.id, appointmentId);
    } catch (err) {
      const message = (err as Error).message;
      const permanent =
        err instanceof KommoPermanentError ||
        (err instanceof KommoApiError && !err.retryable) ||
        event.attempts >= MAX_ATTEMPTS;
      this.logger.warn(`Evento Kommo ${event.id} (tentativa ${event.attempts}): ${message}`);
      try {
        if (permanent) {
          await this.events.markFailed(event.id, message);
        } else {
          const next = new Date(Date.now() + backoffSeconds(event.attempts) * 1000);
          await this.events.scheduleRetry(event.id, message, next);
        }
      } catch (markErr) {
        // O lease expira e o evento volta a ser reivindicado.
        this.logger.error(`Falha ao atualizar evento ${event.id}: ${(markErr as Error).message}`);
      }
    }
  }
}
```

`app.module.ts`: `import { ScheduleModule } from '@nestjs/schedule';` e `ScheduleModule.forRoot()` em `imports`.
`kommo.module.ts`: adicionar `KommoWorkerService` aos providers.

- [ ] **Step 5:** Run o mesmo comando → PASS. Depois `npx vitest run && npx tsc --noEmit`.

- [ ] **Step 6: Teste ponta a ponta manual (staging + conta Kommo de teste)**

1. Com a integração cadastrada (Task 9 ou SQL), mover um lead de teste para "agendado" com data e `14:30`.
2. Em até ~10s: evento `done`, agendamento com `kommo_lead_id`, nota no lead.
3. Mover o lead para outra etapa e voltar → mesmo agendamento atualizado + linha em `appointment_history`.
4. Marcar o agendamento como `attended` e repetir → agendamento novo.
5. Lead com horário `manhã` → 00:00, `needs_review=true`, nota "horário a confirmar".
6. Duas instâncias da API e 20 leads → 20 eventos `done`, nenhum agendamento duplicado.

- [ ] **Step 7: Commit**

```bash
git add package.json package-lock.json src/app.module.ts src/modules/kommo
git commit -m "feat(kommo): worker com claim SKIP LOCKED, retry e backoff"
```

---

### Task 9: Cadastro da integração (super_admin) e documentação

**Files:**
- Create: `src/modules/kommo/dto/kommo-integration.dto.ts`
- Create: `src/modules/kommo/kommo-admin.service.ts`, `kommo-admin.service.spec.ts`
- Create: `src/modules/kommo/kommo-admin.controller.ts`
- Create: `docs/KOMMO.md`
- Modify: `src/modules/kommo/kommo.module.ts`, `db/migrations/README.md`, `.env.example` (se existir)

**Interfaces:**
- Consumes: `KommoIntegrationRepository.{findActiveByCompany, create, update}`, `KommoCryptoService.{generateTenantToken, hashTenantToken, encrypt}`.
- Produces:
  - `PUT /companies/:companyId/kommo-integration` → `{ id, webhook_path? }`; `webhook_path` só na criação (o token aparece uma única vez).
  - `POST /companies/:companyId/kommo-integration/rotate-token` → `{ webhook_path }`.
  - Nunca devolve `access_token`, `access_token_encrypted` nem hash.

- [ ] **Step 1: DTO**

```ts
import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsInt, IsOptional, IsString, IsUUID, Matches, MinLength } from 'class-validator';

export class UpsertKommoIntegrationDto {
  @ApiProperty()
  @IsUUID()
  company_unit_id: string;

  @ApiProperty({ description: 'Usuário técnico com acesso à unidade' })
  @IsUUID()
  service_user_id: string;

  @ApiProperty({ example: 'oticaszyros' })
  @Matches(/^[a-z0-9-]+$/)
  subdomain: string;

  @ApiPropertyOptional({ description: 'Long-lived token com escopo de escrita; obrigatório na criação' })
  @IsOptional()
  @IsString()
  @MinLength(20)
  access_token?: string;

  @ApiProperty({ example: 14505231 })
  @IsInt()
  pipeline_id: number;

  @ApiProperty({ example: 112039795 })
  @IsInt()
  scheduled_status_id: number;

  @ApiProperty({ example: 614091 })
  @IsInt()
  date_field_id: number;

  @ApiProperty({ example: 614093 })
  @IsInt()
  time_field_id: number;

  @ApiPropertyOptional({ example: 566124 })
  @IsOptional()
  @IsInt()
  referral_field_id?: number;

  @ApiProperty({ example: 268220 })
  @IsInt()
  phone_field_id: number;
}
```

- [ ] **Step 2: Teste que falha**

```ts
import { BadRequestException, NotFoundException } from '@nestjs/common';
import { KommoAdminService } from './kommo-admin.service';

const dto = {
  company_unit_id: 'unit-1',
  service_user_id: 'svc-1',
  subdomain: 'oticaszyros',
  access_token: 'a'.repeat(40),
  pipeline_id: 14505231,
  scheduled_status_id: 112039795,
  date_field_id: 614091,
  time_field_id: 614093,
  referral_field_id: 566124,
  phone_field_id: 268220,
};

describe('KommoAdminService', () => {
  let repo: any;
  let crypto: any;
  let service: KommoAdminService;

  beforeEach(() => {
    repo = {
      findActiveByCompany: vi.fn().mockResolvedValue(null),
      create: vi.fn().mockResolvedValue({ id: 'int-1' }),
      update: vi.fn().mockResolvedValue({ id: 'int-1' }),
    };
    crypto = {
      generateTenantToken: vi.fn().mockReturnValue('tok'),
      hashTenantToken: vi.fn().mockReturnValue('hash'),
      encrypt: vi.fn().mockReturnValue('enc'),
    };
    service = new KommoAdminService(repo, crypto);
  });

  it('cria com token criptografado e devolve o caminho do webhook uma vez', async () => {
    await expect(service.upsert('comp-1', dto)).resolves.toEqual({
      id: 'int-1',
      webhook_path: '/kommo/agendamento/tok',
    });
    const saved = repo.create.mock.calls[0][0];
    expect(saved).toMatchObject({
      company_id: 'comp-1',
      access_token_encrypted: 'enc',
      tenant_token_hash: 'hash',
    });
    expect(saved).not.toHaveProperty('access_token');
  });

  it('criação sem access_token → 400', async () => {
    await expect(
      service.upsert('comp-1', { ...dto, access_token: undefined }),
    ).rejects.toBeInstanceOf(BadRequestException);
  });

  it('atualização sem access_token mantém o token e não gera tenant token', async () => {
    repo.findActiveByCompany.mockResolvedValue({ id: 'int-1' });
    await expect(
      service.upsert('comp-1', { ...dto, access_token: undefined }),
    ).resolves.toEqual({ id: 'int-1' });
    expect(repo.update.mock.calls[0][1]).not.toHaveProperty('access_token_encrypted');
    expect(crypto.generateTenantToken).not.toHaveBeenCalled();
  });

  it('rotaciona tenant token', async () => {
    repo.findActiveByCompany.mockResolvedValue({ id: 'int-1' });
    await expect(service.rotateToken('comp-1')).resolves.toEqual({
      webhook_path: '/kommo/agendamento/tok',
    });
    expect(repo.update).toHaveBeenCalledWith('int-1', { tenant_token_hash: 'hash' });
  });

  it('rotacionar sem integração → 404', async () => {
    await expect(service.rotateToken('comp-1')).rejects.toBeInstanceOf(NotFoundException);
  });
});
```

- [ ] **Step 3:** Run `npx vitest run src/modules/kommo/kommo-admin.service.spec.ts` → FAIL.

- [ ] **Step 4: Implementar**

`kommo-admin.service.ts`:

```ts
import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { UpsertKommoIntegrationDto } from './dto/kommo-integration.dto';
import { KommoCryptoService } from './kommo-crypto.service';
import { KommoIntegrationRepository } from './repositories/kommo-integration.repository';

const WEBHOOK_PREFIX = '/kommo/agendamento/';

@Injectable()
export class KommoAdminService {
  constructor(
    private readonly repo: KommoIntegrationRepository,
    private readonly crypto: KommoCryptoService,
  ) {}

  async upsert(
    companyId: string,
    dto: UpsertKommoIntegrationDto,
  ): Promise<{ id: string; webhook_path?: string }> {
    const { access_token, ...fields } = dto;
    const config = { ...fields, referral_field_id: fields.referral_field_id ?? null };
    const existing = await this.repo.findActiveByCompany(companyId);

    if (existing) {
      const updated = await this.repo.update(existing.id, {
        ...config,
        ...(access_token ? { access_token_encrypted: this.crypto.encrypt(access_token) } : {}),
      });
      return { id: updated.id };
    }

    if (!access_token) {
      throw new BadRequestException('access_token é obrigatório ao criar a integração');
    }
    const tenantToken = this.crypto.generateTenantToken();
    const created = await this.repo.create({
      ...config,
      company_id: companyId,
      access_token_encrypted: this.crypto.encrypt(access_token),
      tenant_token_hash: this.crypto.hashTenantToken(tenantToken),
    });
    return { id: created.id, webhook_path: WEBHOOK_PREFIX + tenantToken };
  }

  async rotateToken(companyId: string): Promise<{ webhook_path: string }> {
    const existing = await this.repo.findActiveByCompany(companyId);
    if (!existing) {
      throw new NotFoundException('Integração Kommo não encontrada para esta empresa');
    }
    const tenantToken = this.crypto.generateTenantToken();
    await this.repo.update(existing.id, {
      tenant_token_hash: this.crypto.hashTenantToken(tenantToken),
    });
    return { webhook_path: WEBHOOK_PREFIX + tenantToken };
  }
}
```

`kommo-admin.controller.ts` (copiar de `src/modules/companies/companies.controller.ts` o caminho exato do import de `JwtAuthGuard`):

```ts
import { Body, Controller, HttpCode, Param, ParseUUIDPipe, Post, Put, UseGuards } from '@nestjs/common';
import { ApiBearerAuth, ApiTags } from '@nestjs/swagger';
import { UserRole } from '@/common/enums';
import { Roles } from '@/modules/auth/decorators/roles.decorator';
import { JwtAuthGuard } from '@/modules/auth/guards/jwt-auth.guard';
import { RolesGuard } from '@/modules/auth/guards/roles.guard';
import { UpsertKommoIntegrationDto } from './dto/kommo-integration.dto';
import { KommoAdminService } from './kommo-admin.service';

@ApiTags('Kommo')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard, RolesGuard)
@Roles(UserRole.SUPER_ADMIN)
@Controller('companies/:companyId/kommo-integration')
export class KommoAdminController {
  constructor(private readonly service: KommoAdminService) {}

  @Put()
  upsert(
    @Param('companyId', ParseUUIDPipe) companyId: string,
    @Body() dto: UpsertKommoIntegrationDto,
  ) {
    return this.service.upsert(companyId, dto);
  }

  @Post('rotate-token')
  @HttpCode(200)
  rotate(@Param('companyId', ParseUUIDPipe) companyId: string) {
    return this.service.rotateToken(companyId);
  }
}
```

Registrar `KommoAdminController` e `KommoAdminService` em `kommo.module.ts`.

- [ ] **Step 5: `docs/KOMMO.md`** com estas seções:
  1. **Pré-requisitos:** aplicar `0009` e `0010`; gerar `KOMMO_ENCRYPTION_KEY` com `openssl rand -base64 32`, a mesma em todas as réplicas (perder a chave = recadastrar os tokens).
  2. **Usuário técnico:** criar usuário role `attendant` com acesso à unidade da ótica → `service_user_id`.
  3. **No Kommo:** criar integração privada e gerar long-lived token com escopo de **escrita** (notas).
  4. **Cadastro:** `PUT /companies/{id}/kommo-integration` com o JSON de exemplo (IDs da Zyros) e guardar o `webhook_path`, que aparece uma única vez. Token vazado → `rotate-token` e atualizar o Salesbot.
  5. **Salesbot:** na etapa "agendado", bloco "Enviar um webhook" → `https://<api>/kommo/agendamento/<token>`.
  6. **IDs da Óticas Zyros:** pipeline `14505231`, etapa `112039795`, data `614091`, horário `614093`, indicação `566124`, telefone (contato) `268220`.
  7. **Operação:** SQL para listar eventos `failed`; reprocessar (`UPDATE kommo_events SET status='pending', attempts=0, next_attempt_at=now() WHERE id=...`); listar agendamentos/clientes com `needs_review`.
  8. **Variáveis:** `KOMMO_ENCRYPTION_KEY`, `KOMMO_WORKER_ENABLED`, `KOMMO_WORKER_BATCH_SIZE`.

  Em `db/migrations/README.md`, nada a mudar além de garantir que o texto não contradiz a `0009`/`0010`. Em `.env.example` (se existir), adicionar as três variáveis.

- [ ] **Step 6: Verificar tudo**

Run: `npx vitest run && npx tsc --noEmit && npm run build`
Expected: tudo verde.

- [ ] **Step 7: Commit e PR**

```bash
git add src/modules/kommo docs/KOMMO.md db/migrations/README.md
git commit -m "feat(kommo): cadastro da integração por super_admin e documentação"
git push -u origin feat/kommo-agendamento
gh pr create --title "feat(kommo): integração de agendamento via Salesbot" --body-file <corpo com resumo, testes e checklist de deploy>
```

---

## Nota fora do escopo (descoberta durante o planejamento)

`createClient(...).table` é `undefined` no `@supabase/supabase-js` 2.117 instalado (verificado com `node -e`: `typeof c.table === 'undefined'`). Todos os repositórios existentes usam `this.db.table(...)` e falham em runtime; os testes passam só porque mockam os repositórios. Este plano usa `.from(...)` nos métodos novos. A troca `.table` → `.from` nos repositórios existentes deve ser um PR `fix` separado, de preferência antes deste.
