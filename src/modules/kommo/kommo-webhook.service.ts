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
