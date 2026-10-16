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
