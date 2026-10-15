import { ConflictException, Injectable } from '@nestjs/common';
import { SupabaseService } from '@/core/database/supabase.service';
import {
  Company,
  CompanyUnit,
  CompanyUserLink,
} from '../entities/company.entity';

const COMPANIES_TABLE = 'companies';
const COMPANY_UNITS_TABLE = 'company_units';
const COMPANY_USERS_TABLE = 'company_users';
const UNIQUE_VIOLATION = '23505';

@Injectable()
export class CompanyRepository {
  constructor(private readonly supabase: SupabaseService) {}

  private get db(): any {
    return this.supabase.getClient();
  }

  async create(data: Partial<Company>): Promise<Company> {
    const { data: rows, error } = await this.db
      .table(COMPANIES_TABLE)
      .insert(data)
      .select();

    if (error) {
      if (error.code === UNIQUE_VIOLATION) {
        throw new ConflictException(
          `Company with CNPJ '${data.cnpj}' already exists`,
        );
      }
      throw error;
    }
    return new Company(rows[0]);
  }

  async getAll(
    page: number,
    pageSize: number,
    companyIds?: string[],
  ): Promise<[Company[], number]> {
    let query = this.db
      .table(COMPANIES_TABLE)
      .select('*', { count: 'exact' })
      .is('deleted_at', null);

    if (companyIds && companyIds.length > 0) {
      query = query.in('id', companyIds);
    }

    const { data, count, error } = await query
      .order('created_at', { ascending: false })
      .range((page - 1) * pageSize, page * pageSize - 1);

    if (error) throw error;
    return [(data || []).map((row) => new Company(row)), count || 0];
  }

  async getById(id: string): Promise<Company | null> {
    const { data, error } = await this.db
      .table(COMPANIES_TABLE)
      .select('*')
      .eq('id', id)
      .is('deleted_at', null)
      .maybeSingle();

    if (error) throw error;
    return data ? new Company(data) : null;
  }

  async update(id: string, data: Partial<Company>): Promise<Company | null> {
    const { data: rows, error } = await this.db
      .table(COMPANIES_TABLE)
      .update(data)
      .eq('id', id)
      .is('deleted_at', null)
      .select();

    if (error) {
      if (error.code === UNIQUE_VIOLATION) {
        throw new ConflictException(
          `Company with CNPJ '${data.cnpj}' already exists`,
        );
      }
      throw error;
    }
    return rows && rows.length > 0 ? new Company(rows[0]) : null;
  }

  async softDelete(id: string): Promise<boolean> {
    const { data, error } = await this.db
      .table(COMPANIES_TABLE)
      .update({ deleted_at: new Date().toISOString() })
      .eq('id', id)
      .is('deleted_at', null)
      .select();

    if (error) throw error;
    return Boolean(data && data.length > 0);
  }
}

@Injectable()
export class CompanyUnitRepository {
  constructor(private readonly supabase: SupabaseService) {}

  private get db(): any {
    return this.supabase.getClient();
  }

  async create(data: Partial<CompanyUnit>): Promise<CompanyUnit> {
    const { data: rows, error } = await this.db
      .table(COMPANY_UNITS_TABLE)
      .insert(data)
      .select();

    if (error) {
      if (error.code === UNIQUE_VIOLATION) {
        throw new ConflictException(
          'Unit code or CNPJ already exists for this company',
        );
      }
      throw error;
    }
    return new CompanyUnit(rows[0]);
  }

  async getAll(
    companyId: string,
    page: number,
    pageSize: number,
  ): Promise<[CompanyUnit[], number]> {
    const { data, count, error } = await this.db
      .table(COMPANY_UNITS_TABLE)
      .select('*', { count: 'exact' })
      .eq('company_id', companyId)
      .is('deleted_at', null)
      .order('created_at', { ascending: false })
      .range((page - 1) * pageSize, page * pageSize - 1);

    if (error) throw error;
    return [(data || []).map((row) => new CompanyUnit(row)), count || 0];
  }

  async getById(id: string): Promise<CompanyUnit | null> {
    const { data, error } = await this.db
      .table(COMPANY_UNITS_TABLE)
      .select('*')
      .eq('id', id)
      .is('deleted_at', null)
      .maybeSingle();

    if (error) throw error;
    return data ? new CompanyUnit(data) : null;
  }

  async update(
    id: string,
    data: Partial<CompanyUnit>,
  ): Promise<CompanyUnit | null> {
    const { data: rows, error } = await this.db
      .table(COMPANY_UNITS_TABLE)
      .update(data)
      .eq('id', id)
      .is('deleted_at', null)
      .select();

    if (error) {
      if (error.code === UNIQUE_VIOLATION) {
        throw new ConflictException(
          'Unit code or CNPJ already exists for this company',
        );
      }
      throw error;
    }
    return rows && rows.length > 0 ? new CompanyUnit(rows[0]) : null;
  }

  async softDelete(id: string): Promise<boolean> {
    const { data, error } = await this.db
      .table(COMPANY_UNITS_TABLE)
      .update({ deleted_at: new Date().toISOString() })
      .eq('id', id)
      .is('deleted_at', null)
      .select();

    if (error) throw error;
    return Boolean(data && data.length > 0);
  }
}

@Injectable()
export class CompanyUserRepository {
  constructor(private readonly supabase: SupabaseService) {}

  private get db(): any {
    return this.supabase.getClient();
  }

  async create(data: Partial<CompanyUserLink>): Promise<CompanyUserLink> {
    const { data: rows, error } = await this.db
      .table(COMPANY_USERS_TABLE)
      .insert(data)
      .select();

    if (error) {
      if (error.code === UNIQUE_VIOLATION) {
        throw new ConflictException(
          'User already has an identical access link for this company/unit',
        );
      }
      throw error;
    }
    return new CompanyUserLink(rows[0]);
  }

  async getAllForCompany(
    companyId: string,
    page: number,
    pageSize: number,
  ): Promise<[CompanyUserLink[], number]> {
    const { data, count, error } = await this.db
      .table(COMPANY_USERS_TABLE)
      .select('*', { count: 'exact' })
      .eq('company_id', companyId)
      .is('deleted_at', null)
      .order('created_at', { ascending: false })
      .range((page - 1) * pageSize, page * pageSize - 1);

    if (error) throw error;
    return [(data || []).map((row) => new CompanyUserLink(row)), count || 0];
  }

  async getAllForUser(userId: string): Promise<CompanyUserLink[]> {
    const { data, error } = await this.db
      .table(COMPANY_USERS_TABLE)
      .select('*')
      .eq('user_id', userId)
      .is('deleted_at', null);

    if (error) throw error;
    return (data || []).map((row) => new CompanyUserLink(row));
  }

  async getById(id: string): Promise<CompanyUserLink | null> {
    const { data, error } = await this.db
      .table(COMPANY_USERS_TABLE)
      .select('*')
      .eq('id', id)
      .is('deleted_at', null)
      .maybeSingle();

    if (error) throw error;
    return data ? new CompanyUserLink(data) : null;
  }

  async softDelete(id: string): Promise<boolean> {
    const { data, error } = await this.db
      .table(COMPANY_USERS_TABLE)
      .update({ deleted_at: new Date().toISOString() })
      .eq('id', id)
      .is('deleted_at', null)
      .select();

    if (error) throw error;
    return Boolean(data && data.length > 0);
  }
}
