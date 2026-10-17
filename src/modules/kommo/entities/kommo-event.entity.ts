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
