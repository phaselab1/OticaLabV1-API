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
    const { data: rows, error } = await this.db
      .table(TABLE)
      .insert(data)
      .select();

    if (error) {
      if (error.code === UNIQUE_VIOLATION) {
        throw new ConflictException(
          `Customer with name '${data.full_name}' already exists in this company`,
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
      .table(TABLE)
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

  async getByIdentity(
    companyId: string,
    fullName: string,
  ): Promise<Customer | null> {
    const { data, error } = await this.db
      .table(TABLE)
      .select('*')
      .eq('company_id', companyId)
      .eq('full_name', fullName)
      .is('deleted_at', null)
      .maybeSingle();

    if (error) throw error;
    return data ? new Customer(data) : null;
  }

  async getById(customerId: string): Promise<Customer | null> {
    const { data, error } = await this.db
      .table(TABLE)
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
      .table(TABLE)
      .update(data)
      .eq('id', customerId)
      .is('deleted_at', null)
      .select();

    if (error) {
      if (error.code === UNIQUE_VIOLATION) {
        throw new ConflictException(
          `Customer with name '${data.full_name}' already exists in this company`,
        );
      }
      throw error;
    }
    return rows && rows.length > 0 ? new Customer(rows[0]) : null;
  }

  async softDelete(customerId: string): Promise<boolean> {
    const { data, error } = await this.db
      .table(TABLE)
      .update({ deleted_at: new Date().toISOString() })
      .eq('id', customerId)
      .is('deleted_at', null)
      .select();

    if (error) throw error;
    return Boolean(data && data.length > 0);
  }
}
