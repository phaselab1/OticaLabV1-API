import { Injectable } from '@nestjs/common';
import { SupabaseService } from '@/core/database/supabase.service';

const TABLE = 'login_attempts';

@Injectable()
export class LoginAttemptRepository {
  constructor(private readonly supabase: SupabaseService) {}

  private get db(): any {
    return this.supabase.getClient();
  }

  async countRecentFailures(
    email: string,
    windowMinutes: number,
  ): Promise<number> {
    const since = new Date(
      Date.now() - windowMinutes * 60 * 1000,
    ).toISOString();
    const { count, error } = await this.db
      .from(TABLE)
      .select('id', { count: 'exact' })
      .eq('email', email)
      .eq('success', false)
      .gte('attempted_at', since);

    if (error) throw error;
    return count || 0;
  }

  async record(email: string, success: boolean): Promise<void> {
    const { error } = await this.db.from(TABLE).insert({ email, success });
    if (error) throw error;
  }
}
