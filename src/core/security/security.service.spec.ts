import { SecurityService } from './security.service';

describe('SecurityService', () => {
  let service: SecurityService;

  beforeEach(() => {
    service = new SecurityService();
  });

  it('should hash and verify password correctly', () => {
    const password = 'mySecretPassword123';
    const hash = service.hashPassword(password);

    expect(hash).toBeDefined();
    expect(hash).not.toBe(password);
    expect(service.verifyPassword(password, hash)).toBe(true);
    expect(service.verifyPassword('wrongPassword', hash)).toBe(false);
  });

  it('should verify against dummy password hash safely', () => {
    expect(service.dummyPasswordHash).toBeDefined();
    expect(
      service.verifyPassword('anyPassword', service.dummyPasswordHash),
    ).toBe(false);
  });
});
