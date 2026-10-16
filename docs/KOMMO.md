# Integração Kommo (agendamento via Salesbot)

Quando um lead entra na etapa "agendado" no Kommo, o Salesbot chama o webhook da API. A API grava o evento em `kommo_events` (outbox) e um worker cria/atualiza cliente e agendamento, e escreve uma nota no lead.

## 1. Pré-requisitos

- Aplicar, nesta ordem, `db/migrations/0009_customer_matching.sql` e `db/migrations/0010_kommo_integration.sql`.
- Gerar `KOMMO_ENCRYPTION_KEY` (32 bytes em base64): `openssl rand -base64 32`. A API não sobe sem ela. Use a mesma em todas as réplicas; perder a chave obriga a recadastrar os tokens.

## 2. Usuário técnico

Criar um usuário com role `attendant` e acesso à unidade da ótica. O id dele é o `service_user_id`.

## 3. No Kommo

Criar uma integração privada e gerar um long-lived token com escopo de **escrita** (necessário para notas).

## 4. Cadastro

Como `super_admin`: `PUT /companies/{companyId}/kommo-integration`

```json
{
  "company_unit_id": "<uuid da unidade>",
  "service_user_id": "<uuid do usuário técnico>",
  "subdomain": "oticaszyros",
  "access_token": "<long-lived token>",
  "pipeline_id": 14505231,
  "scheduled_status_id": 112039795,
  "date_field_id": 614091,
  "time_field_id": 614093,
  "referral_field_id": 566124,
  "phone_field_id": 268220
}
```

Na criação a resposta traz `webhook_path`, que aparece **uma única vez**; guarde-o. Em atualizações, `access_token` é opcional (omitido, mantém o atual).

Token do webhook vazado: `POST /companies/{companyId}/kommo-integration/rotate-token` devolve o novo `webhook_path`; atualize o Salesbot.

## 5. Salesbot

Na etapa "agendado", adicionar o bloco "Enviar um webhook" apontando para `https://<api>/kommo/agendamento/<token>`.

## 6. IDs da Óticas Zyros

| Item | ID |
| --- | --- |
| Pipeline | 14505231 |
| Etapa "agendado" | 112039795 |
| Campo data | 614091 |
| Campo horário | 614093 |
| Campo indicação | 566124 |
| Telefone (contato) | 268220 |

## 7. Operação

Eventos com falha:

```sql
SELECT id, attempts, last_error, created_at
FROM kommo_events WHERE status = 'failed' ORDER BY created_at DESC;
```

Reprocessar:

```sql
UPDATE kommo_events
SET status = 'pending', attempts = 0, next_attempt_at = now()
WHERE id = '<id>';
```

Revisão manual. Clientes e agendamentos com `needs_review = true` trazem o motivo em `review_reason` (ex.: "Possível duplicado de <id>", "Horário vazio ou inválido"):

```sql
SELECT id, review_reason FROM customers WHERE needs_review AND deleted_at IS NULL;
SELECT id, review_reason FROM appointments WHERE needs_review AND deleted_at IS NULL;
```

Agendamentos com `scheduled_time_unknown = true` devem ser exibidos como "horário a confirmar".

### Validações manuais pendentes

- `0009`: conferir os valores de similaridade; sinalizar se "João da Silva" × "Maria da Silva" der >= 0.6.
- `0010`: duas sessões concorrentes com `SKIP LOCKED`; upsert executado duas vezes; agendamento atendido seguido de novo evento gera novo agendamento; mesmo horário não duplica.
- Smoke test do webhook com `curl -X POST https://<api>/kommo/agendamento/<token> ...`.
- Teste ponta a ponta em staging com duas réplicas.

## 8. Variáveis

| Variável | Descrição |
| --- | --- |
| `KOMMO_ENCRYPTION_KEY` | Chave AES de 32 bytes em base64 (obrigatória) |
| `KOMMO_WORKER_ENABLED` | `true` liga o worker nesta réplica |
| `KOMMO_WORKER_BATCH_SIZE` | Eventos reivindicados por ciclo (ex.: 10) |
