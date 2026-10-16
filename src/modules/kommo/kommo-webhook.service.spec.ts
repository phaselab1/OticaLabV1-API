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
