import { createClient } from '@supabase/supabase-js';
import { AppointmentRepository } from '@/modules/appointments/repositories/appointment.repository';
import { LoginAttemptRepository } from '@/modules/auth/repositories/login-attempt.repository';
import { CompanyRepository } from '@/modules/companies/repositories/company.repository';
import { CustomerRepository } from '@/modules/customers/repositories/customer.repository';
import { UserRepository } from '@/modules/users/repositories/user.repository';

// Query builder falso: qualquer encadeamento resolve para { data: [], error: null }.
function chain(): any {
  const result = { data: [], count: 0, error: null };
  return new Proxy(() => {}, {
    get: (_t, prop) =>
      prop === 'then' ? (resolve: any) => resolve(result) : () => chain(),
  });
}

// Client real do supabase-js: um método inexistente (ex.: .table) falha aqui, não em produção.
function realClientWithFakeQueries() {
  const client = createClient('http://localhost:54321', 'test-key', {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  vi.spyOn(client, 'from').mockImplementation(() => chain());
  return { getClient: () => client } as any;
}

describe('repositórios usam a API real do supabase-js', () => {
  it.each([
    ['CustomerRepository', CustomerRepository],
    ['AppointmentRepository', AppointmentRepository],
    ['CompanyRepository', CompanyRepository],
    ['UserRepository', UserRepository],
  ])('%s.getById consulta via from()', async (_name, Repo: any) => {
    const supabase = realClientWithFakeQueries();
    await new Repo(supabase).getById('id');
    expect(supabase.getClient().from).toHaveBeenCalled();
  });

  it('LoginAttemptRepository consulta e grava via from()', async () => {
    const supabase = realClientWithFakeQueries();
    const repo = new LoginAttemptRepository(supabase);
    await repo.countRecentFailures('user@example.com' as any, 15 as any).catch(() => undefined);
    await repo.record('user@example.com', false).catch(() => undefined);
    expect(supabase.getClient().from).toHaveBeenCalledTimes(2);
  });
});
