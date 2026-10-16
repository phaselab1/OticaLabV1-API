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
