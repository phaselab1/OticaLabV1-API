import {
  HttpException,
  HttpStatus,
  Injectable,
  UnauthorizedException,
} from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { SecurityService } from '@/core/security/security.service';
import { UsersService } from '@/modules/users/users.service';
import { LoginAttemptRepository } from './repositories/login-attempt.repository';

const MAX_FAILED_ATTEMPTS = 5;
const LOCKOUT_WINDOW_MINUTES = 15;

@Injectable()
export class AuthService {
  constructor(
    private readonly usersService: UsersService,
    private readonly loginAttemptRepository: LoginAttemptRepository,
    private readonly securityService: SecurityService,
    private readonly jwtService: JwtService,
  ) {}

  async login(email: string, pass: string): Promise<string> {
    const recentFailures =
      await this.loginAttemptRepository.countRecentFailures(
        email,
        LOCKOUT_WINDOW_MINUTES,
      );

    if (recentFailures >= MAX_FAILED_ATTEMPTS) {
      throw new HttpException(
        'Mais de 5 tentativas com falha para este e-mail nos últimos 15 minutos. Aguarde antes de tentar novamente.',
        HttpStatus.TOO_MANY_REQUESTS,
      );
    }

    const user = await this.usersService.getByEmail(email);

    // Timing attack prevention: verify against dummy hash if user does not exist
    const passwordHash =
      user && user.password_hash
        ? user.password_hash
        : this.securityService.dummyPasswordHash;
    const isValid = this.securityService.verifyPassword(pass, passwordHash);

    const success = Boolean(user && isValid);
    await this.loginAttemptRepository.record(email, success);

    if (!user || !isValid) {
      throw new UnauthorizedException('E-mail ou senha inválidos.');
    }

    const payload = {
      sub: user.id,
      role: user.role,
    };

    return this.jwtService.sign(payload);
  }
}

