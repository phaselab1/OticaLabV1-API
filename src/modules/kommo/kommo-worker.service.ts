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
