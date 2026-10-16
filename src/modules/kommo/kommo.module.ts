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
