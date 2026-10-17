import { describe, expect, it, vi } from 'vitest';
import { AppointmentRepository } from './appointment.repository';

describe('AppointmentRepository.upsertFromKommo', () => {
  it('chama a função upsert_kommo_appointment com os 12 parâmetros', async () => {
    const rpc = vi.fn().mockResolvedValue({ data: [{ id: 'a1' }], error: null });
    const repo = new AppointmentRepository({ getClient: () => ({ rpc }) } as any);

    const result = await repo.upsertFromKommo({
      companyId: 'c1',
      companyUnitId: 'u1',
      userId: 'usr1',
      kommoLeadId: 42,
      customerId: 'cus1',
      leadFullName: 'Maria',
      leadPhone: '11999999999',
      scheduledAt: '2026-10-20T13:00:00.000Z',
      scheduledTimeUnknown: false,
      notes: 'obs',
      needsReview: true,
      reviewReason: 'motivo',
    });

    expect(rpc).toHaveBeenCalledWith('upsert_kommo_appointment', {
      p_company_id: 'c1',
      p_company_unit_id: 'u1',
      p_user_id: 'usr1',
      p_kommo_lead_id: 42,
      p_customer_id: 'cus1',
      p_lead_full_name: 'Maria',
      p_lead_phone: '11999999999',
      p_scheduled_at: '2026-10-20T13:00:00.000Z',
      p_scheduled_time_unknown: false,
      p_notes: 'obs',
      p_needs_review: true,
      p_review_reason: 'motivo',
    });
    expect(result.id).toBe('a1');
  });
});
