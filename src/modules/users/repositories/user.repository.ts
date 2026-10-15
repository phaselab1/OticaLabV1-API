import { ConflictException, Injectable } from '@nestjs/common';
import { SupabaseService } from '@/core/database/supabase.service';
import { User } from '../entities/user.entity';

const USERS_TABLE = 'users';
const COMPANY_USERS_TABLE = 'company_users';
const UNIQUE_VIOLATION = '23505';

@Injectable()
export class UserRepository {
  constructor(private readonly supabase: SupabaseService) {}

  private get db(): any {
    return this.supabase.getClient();
  }

  async create(data: {
    full_name: string;
    email: string;
    password_hash: string;
    role: string;
  }): Promise<User> {
    const { data: rows, error } = await this.db
      .from(USERS_TABLE)
      .insert(data)
      .select();

    if (error) {
      if (error.code === UNIQUE_VIOLATION) {
        throw new ConflictException(
          `User with email '${data.email}' already exists`,
        );
      }
      throw error;
    }
    return new User(rows[0]);
  }

  async getAll(page: number, pageSize: number): Promise<[User[], number]> {
    const { data, count, error } = await this.db
      .from(USERS_TABLE)
      .select('*', { count: 'exact' })
      .is('deleted_at', null)
      .order('created_at', { ascending: false })
      .range((page - 1) * pageSize, page * pageSize - 1);

    if (error) throw error;
    return [(data || []).map((row) => new User(row)), count || 0];
  }

  async getAccessibleCompanyIds(userId: string): Promise<string[]> {
    const { data, error } = await this.db
      .from(COMPANY_USERS_TABLE)
      .select('company_id')
      .eq('user_id', userId)
      .is('deleted_at', null);

    if (error) throw error;
    const ids = new Set((data || []).map((row) => row.company_id as string));
    return Array.from(ids) as string[];
  }

  async getAllScoped(
    page: number,
    pageSize: number,
    companyIds: string[],
    currentUserId: string,
  ): Promise<[User[], number]> {
    const visibleUserIds = new Set<string>([currentUserId]);
    if (companyIds.length > 0) {
      const { data: links, error: linksError } = await this.db
        .from(COMPANY_USERS_TABLE)
        .select('user_id')
        .in('company_id', companyIds)
        .is('deleted_at', null);

      if (linksError) throw linksError;
      (links || []).forEach((row) => visibleUserIds.add(row.user_id));
    }

    const { data, count, error } = await this.db
      .from(USERS_TABLE)
      .select('*', { count: 'exact' })
      .is('deleted_at', null)
      .in('id', Array.from(visibleUserIds))
      .order('created_at', { ascending: false })
      .range((page - 1) * pageSize, page * pageSize - 1);

    if (error) throw error;
    return [(data || []).map((row) => new User(row)), count || 0];
  }

  async sharesCompanyWith(
    userId: string,
    otherUserId: string,
  ): Promise<boolean> {
    const ownIds = await this.getAccessibleCompanyIds(userId);
    const otherIds = await this.getAccessibleCompanyIds(otherUserId);
    const otherSet = new Set(otherIds);
    return ownIds.some((id) => otherSet.has(id));
  }

  async getById(userId: string): Promise<User | null> {
    const { data, error } = await this.db
      .from(USERS_TABLE)
      .select('*')
      .eq('id', userId)
      .is('deleted_at', null)
      .maybeSingle();

    if (error) throw error;
    return data ? new User(data) : null;
  }

  async getByEmail(email: string): Promise<User | null> {
    const { data, error } = await this.db
      .from(USERS_TABLE)
      .select('*')
      .eq('email', email)
      .is('deleted_at', null)
      .maybeSingle();

    if (error) throw error;
    return data ? new User(data) : null;
  }

  async update(userId: string, data: Partial<User>): Promise<User | null> {
    const { data: rows, error } = await this.db
      .from(USERS_TABLE)
      .update(data)
      .eq('id', userId)
      .is('deleted_at', null)
      .select();

    if (error) {
      if (error.code === UNIQUE_VIOLATION) {
        throw new ConflictException(
          `User with email '${data.email}' already exists`,
        );
      }
      throw error;
    }
    return rows && rows.length > 0 ? new User(rows[0]) : null;
  }

  async softDelete(userId: string): Promise<boolean> {
    const { data, error } = await this.db
      .from(USERS_TABLE)
      .update({ deleted_at: new Date().toISOString() })
      .eq('id', userId)
      .is('deleted_at', null)
      .select();

    if (error) throw error;
    return Boolean(data && data.length > 0);
  }
}
