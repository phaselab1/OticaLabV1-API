import { KommoApiError } from './kommo-client';
import { KommoEvent } from './entities/kommo-event.entity';
import { KommoIntegration } from './entities/kommo-integration.entity';
import {
  KommoEventProcessorService,
  KommoPermanentError,
} from './kommo-event-processor.service';

const LOCAL_MIDNIGHT = Date.UTC(2026, 9, 20, 3) / 1000;

describe('KommoEventProcessorService', () => {
  const integration = new KommoIntegration({
    id: 'int-1',
    company_id: 'comp-1',
    company_unit_id: 'unit-1',
    service_user_id: 'svc-1',
    subdomain: 'zyros',
    access_token_encrypted: 'enc',
    date_field_id: 614091,
    time_field_id: 614093,
    referral_field_id: 566124,
    phone_field_id: 268220,
    timezone: 'America/Araguaina',
    deleted_at: null,
  });
  const event = new KommoEvent({ id: 'ev-1', integration_id: 'int-1', kommo_lead_id: 55 });

  let integrations: any;
  let crypto: any;
  let client: any;
  let customers: any;
  let appointments: any;
  let service: KommoEventProcessorService;

  function lead(time: unknown = '14:30', date: unknown = LOCAL_MIDNIGHT) {
    return {
      id: 55,
      name: 'Lead 55',
      custom_fields_values: [
        { field_id: 614091, values: [{ value: date }] },
        { field_id: 614093, values: [{ value: time }] },
        { field_id: 566124, values: [{ value: 'Dra. Ana' }] },
      ],
      _embedded: { contacts: [{ id: 900, is_main: true }] },
    };
  }

  beforeEach(() => {
    integrations = { findById: vi.fn().mockResolvedValue(integration) };
    crypto = { decrypt: vi.fn().mockReturnValue('kommo-token') };
    client = {
      getLead: vi.fn().mockResolvedValue(lead()),
      getContact: vi.fn().mockResolvedValue({
        id: 900,
        name: 'MARIA DA SILVA',
        custom_fields_values: [{ field_id: 268220, values: [{ value: '+55 63 99123-4567' }] }],
      }),
      addLeadNote: vi.fn().mockResolvedValue(undefined),
    };
    customers = {
      resolve: vi.fn().mockResolvedValue({ customerId: 'cust-new', created: true, reviewReason: null }),
    };
    appointments = { upsertFromKommo: vi.fn().mockResolvedValue({ id: 'appt-1' }) };
    service = new KommoEventProcessorService(
      integrations,
      crypto,
      customers,
      appointments,
      () => client,
    );
  });

  it('caminho feliz: resolve cliente, faz upsert e escreve nota', async () => {
    await expect(service.process(event)).resolves.toBe('appt-1');
    expect(customers.resolve).toHaveBeenCalledWith({
      companyId: 'comp-1',
      companyUnitId: 'unit-1',
      userId: 'svc-1',
      fullName: 'Maria da Silva',
      phone: '63991234567',
      kommoContactId: 900,
    });
    expect(appointments.upsertFromKommo).toHaveBeenCalledWith({
      companyId: 'comp-1',
      companyUnitId: 'unit-1',
      userId: 'svc-1',
      kommoLeadId: 55,
      customerId: 'cust-new',
      leadFullName: 'Maria da Silva',
      leadPhone: '63991234567',
      scheduledAt: '2026-10-20T14:30:00-03:00',
      scheduledTimeUnknown: false,
      notes: 'Indicação: Dra. Ana',
      needsReview: false,
      reviewReason: null,
    });
    expect(client.addLeadNote).toHaveBeenCalledWith(
      55,
      'Agendamento registrado no OticaLab para 20/10/2026 às 14:30.',
    );
  });

  it('possível duplicado vira motivo de revisão do agendamento', async () => {
    customers.resolve.mockResolvedValue({
      customerId: 'cust-new',
      created: true,
      reviewReason: 'Possível duplicado de cust-x',
    });
    await service.process(event);
    expect(appointments.upsertFromKommo).toHaveBeenCalledWith(
      expect.objectContaining({ needsReview: true, reviewReason: 'Possível duplicado de cust-x' }),
    );
  });

  it('horário inválido grava 00:00 com revisão', async () => {
    client.getLead.mockResolvedValue(lead('manhã'));
    await service.process(event);
    expect(appointments.upsertFromKommo).toHaveBeenCalledWith(
      expect.objectContaining({
        scheduledAt: '2026-10-20T00:00:00-03:00',
        scheduledTimeUnknown: true,
        needsReview: true,
        reviewReason: 'Horário vazio ou inválido',
      }),
    );
    expect(client.addLeadNote).toHaveBeenCalledWith(
      55,
      'Agendamento registrado no OticaLab para 20/10/2026 (horário a confirmar).\nRevisar: Horário vazio ou inválido',
    );
  });

  it('telefone inválido segue com phone null e revisão', async () => {
    client.getContact.mockResolvedValue({
      id: 900,
      name: 'Maria',
      custom_fields_values: [{ field_id: 268220, values: [{ value: '123' }] }],
    });
    await service.process(event);
    expect(customers.resolve).toHaveBeenCalledWith(expect.objectContaining({ phone: null }));
    expect(appointments.upsertFromKommo).toHaveBeenCalledWith(
      expect.objectContaining({ leadPhone: null, reviewReason: 'Telefone inválido ou ausente' }),
    );
  });

  it('lead sem contato usa o nome do lead', async () => {
    client.getLead.mockResolvedValue({ ...lead(), _embedded: { contacts: [] } });
    await service.process(event);
    expect(client.getContact).not.toHaveBeenCalled();
    expect(customers.resolve).toHaveBeenCalledWith(
      expect.objectContaining({ fullName: 'Lead 55', phone: null, kommoContactId: null }),
    );
    expect(appointments.upsertFromKommo).toHaveBeenCalledWith(
      expect.objectContaining({ leadFullName: 'Lead 55', leadPhone: null }),
    );
  });

  it('data inválida → nota explicando e erro permanente', async () => {
    client.getLead.mockResolvedValue(lead('10:00', null));
    await expect(service.process(event)).rejects.toBeInstanceOf(KommoPermanentError);
    expect(appointments.upsertFromKommo).not.toHaveBeenCalled();
    expect(client.addLeadNote).toHaveBeenCalledWith(
      55,
      'Não foi possível registrar o agendamento no OticaLab: Data do agendamento vazia ou inválida.',
    );
  });

  it('falha ao escrever nota não derruba o processamento', async () => {
    client.addLeadNote.mockRejectedValue(new KommoApiError('x', 500, true));
    await expect(service.process(event)).resolves.toBe('appt-1');
  });

  it('integração removida → erro permanente', async () => {
    integrations.findById.mockResolvedValue(new KommoIntegration({ deleted_at: '2026-01-01' }));
    await expect(service.process(event)).rejects.toBeInstanceOf(KommoPermanentError);
  });

  it('erro do Kommo ao buscar lead propaga para o worker decidir retry', async () => {
    client.getLead.mockRejectedValue(new KommoApiError('x', 503, true));
    await expect(service.process(event)).rejects.toMatchObject({ retryable: true });
  });
});
