import {
  BadRequestException,
  ConflictException,
  ForbiddenException,
  NotFoundException,
  UnauthorizedException,
} from '@nestjs/common';
import { UserRole } from '@/common/enums';
import { User } from '@/modules/users/entities/user.entity';
import { UsersService } from './users.service';

describe('UsersService', () => {
  let service: UsersService;
  let mockUserRepo: any;
  let mockSecurityService: any;

  beforeEach(() => {
    mockUserRepo = {
      create: vi.fn(),
      getAll: vi.fn(),
      getAllScoped: vi.fn(),
      getAccessibleCompanyIds: vi.fn(),
      sharesCompanyWith: vi.fn(),
      getById: vi.fn(),
      getByEmail: vi.fn(),
      update: vi.fn(),
      softDelete: vi.fn(),
    };
    mockSecurityService = {
      hashPassword: vi.fn().mockReturnValue('hashed_password_123'),
    };
    service = new UsersService(mockUserRepo, mockSecurityService);
  });

  describe('create', () => {
    it('hashes password and creates user', async () => {
      mockUserRepo.create.mockResolvedValue(
        new User({
          id: 'user-1',
          full_name: 'Novo Usuário',
          email: 'novo@oticalab.com',
          role: UserRole.ATTENDANT,
        }),
      );

      const user = await service.create({
        full_name: 'Novo Usuário',
        email: 'novo@oticalab.com',
        password: 'plainpassword',
        role: UserRole.ATTENDANT,
      });

      expect(mockSecurityService.hashPassword).toHaveBeenCalledWith('plainpassword');
      expect(mockUserRepo.create).toHaveBeenCalledWith({
        full_name: 'Novo Usuário',
        email: 'novo@oticalab.com',
        password_hash: 'hashed_password_123',
        role: UserRole.ATTENDANT,
      });
      expect(user.id).toBe('user-1');
    });
  });

  describe('getAll', () => {
    it('super_admin sees all users unscoped', async () => {
      const superAdmin = new User({ id: 's-1', role: UserRole.SUPER_ADMIN });
      mockUserRepo.getAll.mockResolvedValue([[new User({ id: 'u-1' })], 1]);

      const result = await service.getAll(superAdmin, 1, 20);
      expect(mockUserRepo.getAll).toHaveBeenCalledWith(1, 20);
      expect(result.items.length).toBe(1);
      expect(result.total).toBe(1);
    });

    it('regular role sees only users with shared company links', async () => {
      const admin = new User({ id: 'a-1', role: UserRole.ADMIN });
      mockUserRepo.getAccessibleCompanyIds.mockResolvedValue(['comp-1']);
      mockUserRepo.getAllScoped.mockResolvedValue([[admin], 1]);

      const result = await service.getAll(admin, 1, 20);
      expect(mockUserRepo.getAllScoped).toHaveBeenCalledWith(1, 20, ['comp-1'], 'a-1');
      expect(result.items.length).toBe(1);
    });
  });

  describe('getById', () => {
    it('throws NotFoundException if user does not exist', async () => {
      mockUserRepo.getById.mockResolvedValue(null);
      await expect(
        service.getById('nonexistent', new User({ id: 'u-1', role: UserRole.SUPER_ADMIN })),
      ).rejects.toThrow(NotFoundException);
    });

    it('allows super_admin to view any user', async () => {
      const target = new User({ id: 'target-1', role: UserRole.ATTENDANT });
      mockUserRepo.getById.mockResolvedValue(target);

      const res = await service.getById('target-1', new User({ id: 's-1', role: UserRole.SUPER_ADMIN }));
      expect(res.id).toBe('target-1');
    });

    it('allows user to view themselves', async () => {
      const self = new User({ id: 'u-1', role: UserRole.ATTENDANT });
      mockUserRepo.getById.mockResolvedValue(self);

      const res = await service.getById('u-1', self);
      expect(res.id).toBe('u-1');
    });

    it('throws ForbiddenException if non-super_admin does not share company with target', async () => {
      const caller = new User({ id: 'caller-1', role: UserRole.ATTENDANT });
      const target = new User({ id: 'target-1', role: UserRole.ATTENDANT });
      mockUserRepo.getById.mockResolvedValue(target);
      mockUserRepo.sharesCompanyWith.mockResolvedValue(false);

      await expect(service.getById('target-1', caller)).rejects.toThrow(ForbiddenException);
    });
  });

  describe('update and delete', () => {
    it('throws NotFoundException when updating nonexistent user', async () => {
      mockUserRepo.update.mockResolvedValue(null);
      await expect(service.update('u-99', { full_name: 'Novo' })).rejects.toThrow(NotFoundException);
    });

    it('throws NotFoundException when deleting nonexistent user', async () => {
      mockUserRepo.softDelete.mockResolvedValue(false);
      await expect(service.delete('u-99')).rejects.toThrow(NotFoundException);
    });
  });
});

