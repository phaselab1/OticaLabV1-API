import { randomBytes } from 'node:crypto';
import { KommoCryptoService } from './kommo-crypto.service';

function make(key = randomBytes(32).toString('base64')) {
  const config = { get: vi.fn().mockReturnValue(key) } as any;
  return new KommoCryptoService(config);
}

describe('KommoCryptoService', () => {
  it('criptografa e descriptografa', () => {
    const svc = make();
    const enc = svc.encrypt('long-lived-token');
    expect(enc).not.toContain('long-lived-token');
    expect(svc.decrypt(enc)).toBe('long-lived-token');
  });

  it('cada encrypt usa IV novo', () => {
    const svc = make();
    expect(svc.encrypt('x')).not.toBe(svc.encrypt('x'));
  });

  it('falha com chave diferente', () => {
    const enc = make().encrypt('x');
    expect(() => make().decrypt(enc)).toThrow();
  });

  it('tenant token tem formato fixo e hash determinístico', () => {
    const svc = make();
    const token = svc.generateTenantToken();
    expect(token).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(svc.hashTenantToken(token)).toBe(svc.hashTenantToken(token));
    expect(svc.hashTenantToken(token)).toMatch(/^[0-9a-f]{64}$/);
  });

  it('recusa chave com tamanho errado', () => {
    expect(() => make(Buffer.from('curta').toString('base64'))).toThrow(
      'KOMMO_ENCRYPTION_KEY',
    );
  });
});
