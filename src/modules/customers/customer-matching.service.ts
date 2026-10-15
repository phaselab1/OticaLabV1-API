import { ConflictException, Injectable } from '@nestjs/common';
import { phoneVariants } from '@/common/utils/phone.util';
import { classifyCustomerMatch } from './customer-matching';
import { CustomerRepository } from './repositories/customer.repository';

export interface ResolveCustomerInput {
  companyId: string;
  companyUnitId: string;
  userId: string;
  fullName: string;
  phone: string | null;
  kommoContactId?: number | null;
}

export interface ResolvedCustomer {
  customerId: string;
  created: boolean;
  reviewReason: string | null;
}

@Injectable()
export class CustomerMatchingService {
  constructor(private readonly repo: CustomerRepository) {}

  async resolve(input: ResolveCustomerInput): Promise<ResolvedCustomer> {
    const contactId = input.kommoContactId ?? null;

    if (contactId) {
      const linked = await this.repo.findByKommoContactId(input.companyId, contactId);
      if (linked) return { customerId: linked.id, created: false, reviewReason: null };
    }

    const match = input.phone
      ? classifyCustomerMatch(
          await this.repo.matchByPhone(input.companyId, phoneVariants(input.phone), input.fullName),
        )
      : ({ kind: 'new' } as const);

    if (match.kind === 'reuse') {
      if (contactId) await this.repo.linkKommoContact(match.id, contactId, input.userId);
      return { customerId: match.id, created: false, reviewReason: null };
    }

    const reviewReason =
      match.kind === 'possible_duplicate' ? `Possível duplicado de ${match.id}` : null;
    try {
      const created = await this.repo.create({
        company_id: input.companyId,
        company_unit_id: input.companyUnitId,
        full_name: input.fullName,
        phone: input.phone,
        kommo_contact_id: contactId,
        needs_review: reviewReason !== null,
        review_reason: reviewReason,
        created_by_user_id: input.userId,
        updated_by_user_id: input.userId,
      });
      return { customerId: created.id, created: true, reviewReason };
    } catch (err) {
      // O único índice único restante em customers é o do contato Kommo: outro evento venceu a corrida.
      if (err instanceof ConflictException && contactId) {
        const winner = await this.repo.findByKommoContactId(input.companyId, contactId);
        if (winner) return { customerId: winner.id, created: false, reviewReason: null };
      }
      throw err;
    }
  }
}
