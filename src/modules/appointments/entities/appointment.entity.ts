import { AppointmentStatus } from '@/common/enums';

export class Appointment {
  id: string;
  company_id: string;
  company_unit_id: string;
  lead_full_name: string;
  lead_phone: string | null;
  customer_id: string | null;
  created_by_user_id: string;
  updated_by_user_id: string;
  scheduled_at: string;
  status: AppointmentStatus;
  notes: string | null;
  kommo_lead_id: number | null;
  needs_review: boolean;
  review_reason: string | null;
  scheduled_time_unknown: boolean;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;

  constructor(partial: Partial<Appointment>) {
    Object.assign(this, partial);
  }
}

export class AppointmentHistoryEntry {
  id: string;
  appointment_id: string;
  changed_by_user_id: string;
  previous_scheduled_at: string;
  new_scheduled_at: string;
  previous_status: AppointmentStatus;
  new_status: AppointmentStatus;
  notes: string | null;
  changed_at: string;

  constructor(partial: Partial<AppointmentHistoryEntry>) {
    Object.assign(this, partial);
  }
}

