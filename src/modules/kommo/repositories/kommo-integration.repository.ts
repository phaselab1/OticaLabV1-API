import { Injectable } from '@nestjs/common';
import { SupabaseService } from '@/core/database/supabase.service';
import { KommoIntegration } from '../entities/kommo-integration.entity';

const TABLE = 'kommo_integrations';

@Injectable()
export class KommoIntegrationRepository {
  constructor(private readonly supabase: SupabaseService) {}

  private get db(): any {
    return this.supabase.getClient();
  }

  async findActiveByTokenHash(hash: string): Promise<KommoIntegration | null> {
    const { data, error } = await this.db
      .from(TABLE)
      .select('*')
      .eq('tenant_token_hash', hash)
      .is('deleted_at', null)
      .maybeSingle();
    if (error) throw error;
    return data ? new KommoIntegration(data) : null;
  }

  async findById(id: string): Promise<KommoIntegration | null> {
    const { data, error } = await this.db.from(TABLE).select('*').eq('id', id).maybeSingle();
    if (error) throw error;
    return data ? new KommoIntegration(data) : null;
  }

  async findActiveByCompany(companyId: string): Promise<KommoIntegration | null> {
    const { data, error } = await this.db
      .from(TABLE)
      .select('*')
      .eq('company_id', companyId)
      .is('deleted_at', null)
      .maybeSingle();
    if (error) throw error;
    return data ? new KommoIntegration(data) : null;
  }

  async create(data: Partial<KommoIntegration>): Promise<KommoIntegration> {
    const { data: rows, error } = await this.db.from(TABLE).insert(data).select();
    if (error) throw error;
    return new KommoIntegration(rows[0]);
  }

  async update(id: string, data: Partial<KommoIntegration>): Promise<KommoIntegration> {
    const { data: rows, error } = await this.db
      .from(TABLE)
      .update({ ...data, updated_at: new Date().toISOString() })
      .eq('id', id)
      .select();
    if (error) throw error;
    return new KommoIntegration(rows[0]);
  }
}
