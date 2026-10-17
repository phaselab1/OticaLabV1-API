import {
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { PageDto } from '@/common/dto/pagination.dto';
import { UserRole } from '@/common/enums';
import { SecurityService } from '@/core/security/security.service';
import { CreateUserDto, UpdateUserDto } from './dto/user.dto';
import { User } from './entities/user.entity';
import { UserRepository } from './repositories/user.repository';

@Injectable()
export class UsersService {
  constructor(
    private readonly userRepository: UserRepository,
    private readonly securityService: SecurityService,
  ) {}

  async create(data: CreateUserDto): Promise<User> {
    const passwordHash = this.securityService.hashPassword(data.password);
    return this.userRepository.create({
      full_name: data.full_name,
      email: data.email,
      password_hash: passwordHash,
      role: data.role || UserRole.ATTENDANT,
    });
  }

  async getAll(
    currentUser: User,
    page: number = 1,
    pageSize: number = 20,
  ): Promise<PageDto<User>> {
    let users: User[];
    let total: number;

    if (currentUser.role === UserRole.SUPER_ADMIN) {
      [users, total] = await this.userRepository.getAll(page, pageSize);
    } else {
      const companyIds = await this.userRepository.getAccessibleCompanyIds(
        currentUser.id,
      );
      [users, total] = await this.userRepository.getAllScoped(
        page,
        pageSize,
        companyIds,
        currentUser.id,
      );
    }

    return new PageDto(users, page, pageSize, total);
  }

  async getById(userId: string, currentUser: User): Promise<User> {
    const user = await this.userRepository.getById(userId);
    if (!user) {
      throw new NotFoundException(`User '${userId}' not found`);
    }

    const isSelf = user.id === currentUser.id;
    if (currentUser.role !== UserRole.SUPER_ADMIN && !isSelf) {
      const shares = await this.userRepository.sharesCompanyWith(
        currentUser.id,
        userId,
      );
      if (!shares) {
        throw new ForbiddenException(
          `No shared company access with user ${userId}`,
        );
      }
    }

    return user;
  }

  async update(userId: string, data: UpdateUserDto): Promise<User> {
    const updatePayload: Partial<User> = {};
    if (data.full_name !== undefined) updatePayload.full_name = data.full_name;
    if (data.email !== undefined) updatePayload.email = data.email;
    if (data.role !== undefined) updatePayload.role = data.role;

    const updated = await this.userRepository.update(userId, updatePayload);
    if (!updated) {
      throw new NotFoundException(`User '${userId}' not found`);
    }
    return updated;
  }

  async delete(userId: string): Promise<void> {
    const deleted = await this.userRepository.softDelete(userId);
    if (!deleted) {
      throw new NotFoundException(`User '${userId}' not found`);
    }
  }

  async getByEmail(email: string): Promise<User | null> {
    return this.userRepository.getByEmail(email);
  }

  async getByIdDirect(id: string): Promise<User | null> {
    return this.userRepository.getById(id);
  }
}
