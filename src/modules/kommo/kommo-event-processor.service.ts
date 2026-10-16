import { Inject, Injectable, Logger } from '@nestjs/common';
import { formatTitleCase } from '@/common/utils/text.util';
import { AppointmentRepository } from '@/modules/appointments/repositories/appointment.repository';
import { CustomerMatchingService } from '@/modules/customers/customer-matching.service';
import { KommoEvent } from './entities/kommo-event.entity';
import { KommoClient, fieldValue } from './kommo-client';
import { KommoCryptoService } from './kommo-crypto.service';
import { KommoIntegrationRepository } from './repositories/kommo-integration.repository';
import { normalizePhone } from '@/common/utils/phone.util';
import { parseSchedule } from './utils/kommo-schedule.util';

export class KommoPermanentError extends Error {}

export type KommoClientFactory = (subdomain: string, token: string) => KommoClient;
export const KOMMO_CLIENT_FACTORY = 'KOMMO_CLIENT_FACTORY';

const REVIEW = {
  time: 'Horário vazio ou inválido',
  phone: 'Telefone inválido ou ausente',
  name: 'Lead sem nome',
};

@Injectable()
export class KommoEventProcessorService {
  private readonly logger = new Logger(KommoEventProcessorService.name);

  constructor(
    private readonly integrations: KommoIntegrationRepository,
    private readonly crypto: KommoCryptoService,
    private readonly customers: CustomerMatchingService,
    private readonly appointments: AppointmentRepository,
    @Inject(KOMMO_CLIENT_FACTORY) private readonly clientFactory: KommoClientFactory,
  ) {}

  async process(event: KommoEvent): Promise<string> {
    const integration = await this.integrations.findById(event.integration_id);
    if (!integration || integration.deleted_at) {
      throw new KommoPermanentError('Integração desativada');
    }

    const client = this.clientFactory(
      integration.subdomain,
      this.crypto.decrypt(integration.access_token_encrypted),
    );
    const leadId = Number(event.kommo_lead_id);
    const lead = await client.getLead(leadId);

    const schedule = parseSchedule(
      fieldValue(lead.custom_fields_values, integration.date_field_id),
      fieldValue(lead.custom_fields_values, integration.time_field_id),
      integration.timezone,
    );
    if (schedule.ok === false) {
      await this.safeNote(
        client,
        leadId,
        `Não foi possível registrar o agendamento no OticaLab: ${schedule.reason}.`,
      );
      throw new KommoPermanentError(schedule.reason);
    }

    const contacts = lead._embedded?.contacts ?? [];
    const mainContact = contacts.find((c) => c.is_main) ?? contacts[0];
    const contact = mainContact ? await client.getContact(mainContact.id) : null;

    const reasons: string[] = [];
    if (schedule.timeUnknown) reasons.push(REVIEW.time);

    const rawPhone = contact
      ? fieldValue(contact.custom_fields_values, integration.phone_field_id)
      : null;
    const phone = normalizePhone(rawPhone === null ? null : String(rawPhone));
    if (!phone) reasons.push(REVIEW.phone);

    let fullName = formatTitleCase(contact?.name || lead.name);
    if (!fullName) {
      fullName = 'Sem Nome';
      reasons.push(REVIEW.name);
    }

    const resolved = await this.customers.resolve({
      companyId: integration.company_id,
      companyUnitId: integration.company_unit_id,
      userId: integration.service_user_id,
      fullName,
      phone,
      kommoContactId: contact?.id ?? null,
    });
    if (resolved.reviewReason) reasons.push(resolved.reviewReason);

    const referral = fieldValue(lead.custom_fields_values, integration.referral_field_id);
    const appointment = await this.appointments.upsertFromKommo({
      companyId: integration.company_id,
      companyUnitId: integration.company_unit_id,
      userId: integration.service_user_id,
      kommoLeadId: leadId,
      customerId: resolved.customerId,
      leadFullName: fullName,
      leadPhone: phone,
      scheduledAt: schedule.scheduledAt,
      scheduledTimeUnknown: schedule.timeUnknown,
      notes: referral ? `Indicação: ${referral}` : null,
      needsReview: reasons.length > 0,
      reviewReason: reasons.length > 0 ? reasons.join('; ') : null,
    });

    await this.safeNote(
      client,
      leadId,
      this.successNote(schedule.scheduledAt, schedule.timeUnknown, reasons),
    );
    return appointment.id;
  }

  private successNote(scheduledAt: string, timeUnknown: boolean, reasons: string[]): string {
    const [date, time] = scheduledAt.slice(0, 16).split('T');
    const [y, m, d] = date.split('-');
    const when = timeUnknown ? `${d}/${m}/${y} (horário a confirmar)` : `${d}/${m}/${y} às ${time}`;
    const review = reasons.length > 0 ? `\nRevisar: ${reasons.join('; ')}` : '';
    return `Agendamento registrado no OticaLab para ${when}.${review}`;
  }

  private async safeNote(client: KommoClient, leadId: number, text: string): Promise<void> {
    try {
      await client.addLeadNote(leadId, text);
    } catch (err) {
      this.logger.warn(`Falha ao criar nota no lead ${leadId}: ${(err as Error).message}`);
    }
  }
}
