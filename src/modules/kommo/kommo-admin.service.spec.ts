import { BadRequestException, NotFoundException } from '@nestjs/common';
import { KommoAdminService } from './kommo-admin.service';

const dto = {
  company_unit_id: 'unit-1',
  service_user_id: 'svc-1',
  subdomain: 'oticaszyros',
  access_token: 'a'.repeat(40),
  pipeline_id: 14505231,
  scheduled_status_id: 112039795,
  date_field_id: 614091,
  time_field_id: 614093,
  referral_field_id: 566124,
  phone_field_id: 268220,
};

describe('KommoAdminService', () => {
  let repo: any;
  let crypto: any;
  let service: KommoAdminService;

  beforeEach(() => {
    repo = {
      findActiveByCompany: vi.fn().mockResolvedValue(null),
      create: vi.fn().mockResolvedValue({ id: 'int-1' }),
      update: vi.fn().mockResolvedValue({ id: 'int-1' }),
    };
    crypto = {
      generateTenantToken: vi.fn().mockReturnValue('tok'),
      hashTenantToken: vi.fn().mockReturnValue('hash'),
      encrypt: vi.fn().mockReturnValue('enc'),
    };
    service = new KommoAdminService(repo, crypto);
  });

  it('cria com token criptografado e devolve o caminho do webhook uma vez', async () => {
    await expect(service.upsert('comp-1', dto)).resolves.toEqual({
      id: 'int-1',
      webhook_path: '/kommo/agendamento/tok',
    });
    const saved = repo.create.mock.calls[0][0];
    expect(saved).toMatchObject({
      company_id: 'comp-1',
      access_token_encrypted: 'enc',
      tenant_token_hash: 'hash',
    });
    expect(saved).not.toHaveProperty('access_token');
  });

  it('criação sem access_token → 400', async () => {
    await expect(
      service.upsert('comp-1', { ...dto, access_token: undefined }),
    ).rejects.toBeInstanceOf(BadRequestException);
  });

  it('atualização sem access_token mantém o token e não gera tenant token', async () => {
    repo.findActiveByCompany.mockResolvedValue({ id: 'int-1' });
    await expect(
      service.upsert('comp-1', { ...dto, access_token: undefined }),
    ).resolves.toEqual({ id: 'int-1' });
    expect(repo.update.mock.calls[0][1]).not.toHaveProperty('access_token_encrypted');
    expect(crypto.generateTenantToken).not.toHaveBeenCalled();
  });

  it('rotaciona tenant token', async () => {
    repo.findActiveByCompany.mockResolvedValue({ id: 'int-1' });
    await expect(service.rotateToken('comp-1')).resolves.toEqual({
      webhook_path: '/kommo/agendamento/tok',
    });
    expect(repo.update).toHaveBeenCalledWith('int-1', { tenant_token_hash: 'hash' });
  });

  it('rotacionar sem integração → 404', async () => {
    await expect(service.rotateToken('comp-1')).rejects.toBeInstanceOf(NotFoundException);
  });
});
