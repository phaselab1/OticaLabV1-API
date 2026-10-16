import { Module } from '@nestjs/common';
import { AppointmentsModule } from '@/modules/appointments/appointments.module';
import { CustomersModule } from '@/modules/customers/customers.module';
import { KommoClient } from './kommo-client';
import {
  KOMMO_CLIENT_FACTORY,
  KommoEventProcessorService,
} from './kommo-event-processor.service';
import { KommoCryptoService } from './kommo-crypto.service';
import { KommoWebhookController } from './kommo-webhook.controller';
import { KommoWebhookService } from './kommo-webhook.service';
import { KommoEventRepository } from './repositories/kommo-event.repository';
import { KommoIntegrationRepository } from './repositories/kommo-integration.repository';

@Module({
  imports: [CustomersModule, AppointmentsModule],
  controllers: [KommoWebhookController],
  providers: [
    KommoCryptoService,
    KommoWebhookService,
    KommoIntegrationRepository,
    KommoEventRepository,
    KommoEventProcessorService,
    {
      provide: KOMMO_CLIENT_FACTORY,
      useValue: (subdomain: string, token: string) => new KommoClient(subdomain, token),
    },
  ],
})
export class KommoModule {}
