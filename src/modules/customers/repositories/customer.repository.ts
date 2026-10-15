import { ConflictException, Injectable } from '@nestjs/common';
import { SupabaseService } from '@/core/database/supabase.service';
import { Customer } from '../entities/customer.entity';

const TABLE = 'customers';
const UNIQUE_VIOLATION = '23505';

@Injectable()
export class CustomerRepository {
  constructor(private readonly supabase: SupabaseService) {}

  private get db(): any {
    return this.supabase.getClient();
  }

  async create(data: Partial<Customer>): Promise<Customer> {
    // A coluna kommo_contact_id só existe após a migration 0010.
    const { kommo_contact_id: kommoContactId, ...rest } = data;
    const payload = kommoContactId == null ? rest : data;
    const { data: rows, error } = await this.db
      .from(TABLE)
      .insert(payload)
      .select();

    if (error) {
      if (error.code === UNIQUE_VIOLATION) {
        throw new ConflictException(
          'Este contato do Kommo já está vinculado a outro cliente',
        );
      }
      throw error;
    }
    return new Customer(rows[0]);
  }

  async getAll(
    page: number,
    pageSize: number,
    companyId?: string | null,
    companyUnitId?: string | null,
  ): Promise<[Customer[], number]> {
    let query = this.db
      .from(TABLE)
      .select('*', { count: 'exact' })
      .is('deleted_at', null);

    if (companyId) {
      query = query.eq('company_id', companyId);
    }
    if (companyUnitId) {
      query = query.eq('company_unit_id', companyUnitId);
    }

    const { data, count, error } = await query
      .order('created_at', { ascending: false })
      .range((page - 1) * pageSize, page * pageSize - 1);

    if (error) throw error;
    return [(data || []).map((row) => new Customer(row)), count || 0];
  }

  async getById(customerId: string): Promise<Customer | null> {
    const { data, error } = await this.db
      .from(TABLE)
      .select('*')
      .eq('id', customerId)
      .is('deleted_at', null)
      .maybeSingle();

    if (error) throw error;
    return data ? new Customer(data) : null;
  }

  async update(
    customerId: string,
    data: Partial<Customer>,
  ): Promise<Customer | null> {
    const { data: rows, error } = await this.db
      .from(TABLE)
      .update(data)
      .eq('id', customerId)
      .is('deleted_at', null)
      .select();

    if (error) {
      if (error.code === UNIQUE_VIOLATION) {
        throw new ConflictException(
          'Este contato do Kommo já está vinculado a outro cliente',
        );
      }
      throw error;
    }
    return rows && rows.length > 0 ? new Customer(rows[0]) : null;
  }

  async softDelete(customerId: string): Promise<boolean> {
    const { data, error } = await this.db
      .from(TABLE)
      .update({ deleted_at: new Date().toISOString() })
      .eq('id', customerId)
      .is('deleted_at', null)
      .select();

    if (error) throw error;
    return Boolean(data && data.length > 0);
  }

  async matchByPhone(
    companyId: string,
    phones: string[],
    fullName: string,
  ): Promise<{ id: string; score: number }[]> {
    const { data, error } = await this.db.rpc('match_customers_by_phone', {
      p_company_id: companyId,
      p_phones: phones,
      p_full_name: fullName,
    });
    if (error) throw error;
    return (data || []).map((row: any) => ({ id: row.id, score: Number(row.score) }));
  }

  async findByKommoContactId(companyId: string, contactId: number): Promise<Customer | null> {
    const { data, error } = await this.db
      .from(TABLE)
      .select('*')
      .eq('company_id', companyId)
      .eq('kommo_contact_id', contactId)
      .is('deleted_at', null)
      .maybeSingle();
    if (error) throw error;
    return data ? new Customer(data) : null;
  }

  async linkKommoContact(customerId: string, contactId: number, userId: string): Promise<void> {
    const { error } = await this.db
      .from(TABLE)
      .update({ kommo_contact_id: contactId, updated_by_user_id: userId })
      .eq('id', customerId)
      .is('kommo_contact_id', null);
    if (error && error.code !== UNIQUE_VIOLATION) throw error;
  }
}
