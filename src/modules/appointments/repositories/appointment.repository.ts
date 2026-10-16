import { ConflictException, Injectable } from '@nestjs/common';
import { AppointmentStatus } from '@/common/enums';
import { SupabaseService } from '@/core/database/supabase.service';
import {
  Appointment,
  AppointmentHistoryEntry,
} from '../entities/appointment.entity';

const TABLE = 'appointments';
const HISTORY_TABLE = 'appointment_history';
const UPDATE_WITH_HISTORY_FN = 'update_appointment_with_history';
const APPOINTMENT_NOT_FOUND = 'P0002';
const UNIQUE_VIOLATION = '23505';

export interface KommoAppointmentInput {
  companyId: string;
  companyUnitId: string;
  userId: string;
  kommoLeadId: number;
  customerId: string | null;
  leadFullName: string;
  leadPhone: string | null;
  scheduledAt: string;
  scheduledTimeUnknown: boolean;
  notes: string | null;
  needsReview: boolean;
  reviewReason: string | null;
}

@Injectable()
export class AppointmentRepository {
  constructor(private readonly supabase: SupabaseService) {}

  private get db(): any {
    return this.supabase.getClient();
  }

  async create(data: Partial<Appointment>): Promise<Appointment> {
    const { data: rows, error } = await this.db
      .from(TABLE)
      .insert(data)
      .select();

    if (error) {
      if (error.code === UNIQUE_VIOLATION) {
        const subject = data.customer_id
          ? `Customer ${data.customer_id}`
          : data.lead_full_name;
        throw new ConflictException(
          `Appointment conflict: ${subject} already has an active appointment at ${data.scheduled_at}`,
        );
      }
      throw error;
    }
    return new Appointment(rows[0]);
  }

  async getAll(
    page: number,
    pageSize: number,
    companyId?: string | null,
    companyUnitId?: string | null,
    customerId?: string | null,
    status?: AppointmentStatus | null,
  ): Promise<[Appointment[], number]> {
    let query = this.db
      .from(TABLE)
      .select('*', { count: 'exact' })
      .is('deleted_at', null);

    if (companyId) query = query.eq('company_id', companyId);
    if (companyUnitId) query = query.eq('company_unit_id', companyUnitId);
    if (customerId) query = query.eq('customer_id', customerId);
    if (status) query = query.eq('status', status);

    const { data, count, error } = await query
      .order('scheduled_at', { ascending: true })
      .range((page - 1) * pageSize, page * pageSize - 1);

    if (error) throw error;
    return [(data || []).map((row) => new Appointment(row)), count || 0];
  }

  async getById(appointmentId: string): Promise<Appointment | null> {
    const { data, error } = await this.db
      .from(TABLE)
      .select('*')
      .eq('id', appointmentId)
      .is('deleted_at', null)
      .maybeSingle();

    if (error) throw error;
    return data ? new Appointment(data) : null;
  }

  async updateWithHistory(
    appointmentId: string,
    changedByUserId: string,
    options: {
      scheduledAt?: string | null;
      status?: string | null;
      notes?: string | null;
      notesProvided: boolean;
      customerId?: string | null;
      subject?: string | null;
    },
  ): Promise<Appointment | null> {
    const { data, error } = await this.db.rpc(UPDATE_WITH_HISTORY_FN, {
      p_appointment_id: appointmentId,
      p_changed_by_user_id: changedByUserId,
      p_new_scheduled_at: options.scheduledAt || null,
      p_new_status: options.status || null,
      p_new_notes: options.notes || null,
      p_notes_provided: options.notesProvided,
      p_customer_id: options.customerId || null,
    });

    if (error) {
      if (error.code === APPOINTMENT_NOT_FOUND) {
        return null;
      }
      if (error.code === UNIQUE_VIOLATION) {
        const scheduled = options.scheduledAt || 'neste horário';
        const targetSubject = options.subject || 'Este paciente';
        throw new ConflictException(
          `${targetSubject} já tem um agendamento ativo em ${scheduled}`,
        );
      }
      throw error;
    }

    if (!data) return null;
    const rows = Array.isArray(data) ? data : [data];
    return rows.length > 0 ? new Appointment(rows[0]) : null;
  }

  async updateLeadInfo(
    appointmentId: string,
    changedByUserId: string,
    leadFullName?: string | null,
    leadPhone?: string | null,
    leadPhoneProvided: boolean = false,
  ): Promise<Appointment | null> {
    const updateData: any = {
      updated_by_user_id: changedByUserId,
    };
    if (leadFullName !== undefined) {
      updateData.lead_full_name = leadFullName;
    }
    if (leadPhoneProvided) {
      updateData.lead_phone = leadPhone;
    }

    const { data, error } = await this.db
      .from(TABLE)
      .update(updateData)
      .eq('id', appointmentId)
      .is('deleted_at', null)
      .select();

    if (error) throw error;
    return data && data.length > 0 ? new Appointment(data[0]) : null;
  }

  async softDelete(appointmentId: string): Promise<boolean> {
    const nowIso = new Date().toISOString();
    const { data, error } = await this.db
      .from(TABLE)
      .update({ deleted_at: nowIso })
      .eq('id', appointmentId)
      .is('deleted_at', null)
      .select();

    if (error) {
      if (String(error.message || '').includes('is deactivated')) {
        const { data: retryData, error: retryError } = await this.db
          .from(TABLE)
          .update({ deleted_at: nowIso, customer_id: null })
          .eq('id', appointmentId)
          .is('deleted_at', null)
          .select();
        if (retryError) throw retryError;
        return Boolean(retryData && retryData.length > 0);
      }
      throw error;
    }

    return Boolean(data && data.length > 0);
  }
}

@Injectable()
export class AppointmentHistoryRepository {
  constructor(private readonly supabase: SupabaseService) {}

  private get db(): any {
    return this.supabase.getClient();
  }

  async getByAppointmentId(
    appointmentId: string,
    page: number,
    pageSize: number,
  ): Promise<[AppointmentHistoryEntry[], number]> {
    const { data, count, error } = await this.db
      .from(HISTORY_TABLE)
      .select('*', { count: 'exact' })
      .eq('appointment_id', appointmentId)
      .order('changed_at', { ascending: false })
      .range((page - 1) * pageSize, page * pageSize - 1);

    if (error) throw error;
    return [
      (data || []).map((row) => new AppointmentHistoryEntry(row)),
      count || 0,
    ];
  }

  async upsertFromKommo(input: KommoAppointmentInput): Promise<Appointment> {
    const { data, error } = await this.db.rpc('upsert_kommo_appointment', {
      p_company_id: input.companyId,
      p_company_unit_id: input.companyUnitId,
      p_user_id: input.userId,
      p_kommo_lead_id: input.kommoLeadId,
      p_customer_id: input.customerId,
      p_lead_full_name: input.leadFullName,
      p_lead_phone: input.leadPhone,
      p_scheduled_at: input.scheduledAt,
      p_scheduled_time_unknown: input.scheduledTimeUnknown,
      p_notes: input.notes,
      p_needs_review: input.needsReview,
      p_review_reason: input.reviewReason,
    });
    if (error) throw error;
    const rows = Array.isArray(data) ? data : [data];
    return new Appointment(rows[0]);
  }
}
