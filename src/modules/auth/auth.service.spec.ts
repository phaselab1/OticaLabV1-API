import {
  HttpException,
  HttpStatus,
  UnauthorizedException,
} from '@nestjs/common';
import { UserRole } from '@/common/enums';
import { User } from '@/modules/users/entities/user.entity';
import { AuthService } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let mockUsersService: any;
  let mockLoginAttemptRepo: any;
  let mockSecurityService: any;
  let mockJwtService: any;

  beforeEach(() => {
    mockUsersService = {
      getByEmail: vi.fn(),
    };
    mockLoginAttemptRepo = {
      countRecentFailures: vi.fn(),
      record: vi.fn(),
    };
    mockSecurityService = {
      dummyPasswordHash: 'dummy_hash',
      verifyPassword: vi.fn(),
    };
    mockJwtService = {
      sign: vi.fn().mockReturnValue('mocked.jwt.token'),
    };

    service = new AuthService(
      mockUsersService,
      mockLoginAttemptRepo,
      mockSecurityService,
      mockJwtService,
    );
  });

  it('blocks login if user has 5 or more recent failed attempts (HTTP 429)', async () => {
    mockLoginAttemptRepo.countRecentFailures.mockResolvedValue(5);

    await expect(service.login('admin@test.com', 'password')).rejects.toThrow(
      HttpException,
    );
    try {
      await service.login('admin@test.com', 'password');
    } catch (err: any) {
      expect(err.getStatus()).toBe(HttpStatus.TOO_MANY_REQUESTS);
    }
  });

  it('verifies against dummy hash and rejects if user does not exist (timing attack safety)', async () => {
    mockLoginAttemptRepo.countRecentFailures.mockResolvedValue(0);
    mockUsersService.getByEmail.mockResolvedValue(null);
    mockSecurityService.verifyPassword.mockReturnValue(false);

    await expect(service.login('unknown@test.com', 'password')).rejects.toThrow(
      UnauthorizedException,
    );
    expect(mockSecurityService.verifyPassword).toHaveBeenCalledWith(
      'password',
      'dummy_hash',
    );
    expect(mockLoginAttemptRepo.record).toHaveBeenCalledWith(
      'unknown@test.com',
      false,
    );
  });

  it('verifies password and returns signed JWT token on valid credentials', async () => {
    mockLoginAttemptRepo.countRecentFailures.mockResolvedValue(0);
    const user = new User({
      id: 'user-1',
      email: 'user@test.com',
      password_hash: 'real_hash',
      role: UserRole.ADMIN,
    });
    mockUsersService.getByEmail.mockResolvedValue(user);
    mockSecurityService.verifyPassword.mockReturnValue(true);

    const token = await service.login('user@test.com', 'correct_password');

    expect(token).toBe('mocked.jwt.token');
    expect(mockLoginAttemptRepo.record).toHaveBeenCalledWith(
      'user@test.com',
      true,
    );
    expect(mockJwtService.sign).toHaveBeenCalledWith({
      sub: 'user-1',
      role: UserRole.ADMIN,
    });
  });
});

