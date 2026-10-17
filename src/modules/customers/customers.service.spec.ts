import {
  BadRequestException,
  ForbiddenException,
  NotFoundException,
} from '@nestjs/common';
import { UserRole } from '@/common/enums';
import { User } from '@/modules/users/entities/user.entity';
import { CustomersService } from './customers.service';
import { Customer } from './entities/customer.entity';

describe('CustomersService', () => {
  let service: CustomersService;
  let mockCustomerRepo: any;
  let mockCompanyUserService: any;

  beforeEach(() => {
    mockCustomerRepo = {
      create: vi.fn(),
      getAll: vi.fn(),
      getById: vi.fn(),
      getByIdentity: vi.fn(),
      update: vi.fn(),
      softDelete: vi.fn(),
    };
    mockCompanyUserService = {
      resolveCompanyAndUnit: vi.fn(),
      resolveScopeForList: vi.fn(),
      hasUnitAccess: vi.fn(),
    };

    service = new CustomersService(mockCustomerRepo, mockCompanyUserService);
  });

  describe('create', () => {
    it('creates customer with title cased name and resolved company/unit', async () => {
      const user = new User({ id: 'u-1', role: UserRole.ATTENDANT });
      mockCompanyUserService.resolveCompanyAndUnit.mockResolvedValue([
        'comp-1',
        'unit-1',
      ]);
      mockCustomerRepo.create.mockResolvedValue(
        new Customer({
          id: 'cust-1',
          full_name: 'Maria da Silva',
          phone: '11987654321',
          company_id: 'comp-1',
          company_unit_id: 'unit-1',
        }),
      );

      const customer = await service.create(
        {
          full_name: 'maria da silva',
          phone: '11987654321',
        },
        user,
      );

      expect(mockCompanyUserService.resolveCompanyAndUnit).toHaveBeenCalledWith(
        user,
        undefined,
        undefined,
      );
      expect(mockCustomerRepo.create).toHaveBeenCalledWith({
        company_id: 'comp-1',
        company_unit_id: 'unit-1',
        full_name: 'Maria da Silva',
        phone: '11987654321',
        created_by_user_id: 'u-1',
        updated_by_user_id: 'u-1',
      });
      expect(customer.id).toBe('cust-1');
    });
  });

  describe('getAll', () => {
    it('returns empty page when user has no company access (__none__)', async () => {
      const user = new User({ id: 'u-1', role: UserRole.ATTENDANT });
      mockCompanyUserService.resolveScopeForList.mockResolvedValue([
        '__none__',
        '__none__',
      ]);

      const result = await service.getAll(user, 1, 20);
      expect(result.items).toEqual([]);
      expect(result.total).toBe(0);
      expect(mockCustomerRepo.getAll).not.toHaveBeenCalled();
    });

    it('queries repository with resolved scope for tenant', async () => {
      const user = new User({ id: 'u-1', role: UserRole.MANAGER });
      mockCompanyUserService.resolveScopeForList.mockResolvedValue([
        'comp-1',
        'unit-1',
      ]);
      mockCustomerRepo.getAll.mockResolvedValue([[new Customer({ id: 'c-1' })], 1]);

      const result = await service.getAll(user, 1, 20);
      expect(mockCustomerRepo.getAll).toHaveBeenCalledWith(1, 20, 'comp-1', 'unit-1');
      expect(result.items.length).toBe(1);
    });
  });

  describe('getById', () => {
    it('throws NotFoundException if customer does not exist', async () => {
      mockCustomerRepo.getById.mockResolvedValue(null);
      await expect(
        service.getById('nonexistent', new User({ id: 'u-1', role: UserRole.SUPER_ADMIN })),
      ).rejects.toThrow(NotFoundException);
    });

    it('throws ForbiddenException if user has no access to customer unit', async () => {
      const customer = new Customer({
        id: 'c-1',
        company_id: 'comp-1',
        company_unit_id: 'unit-1',
      });
      mockCustomerRepo.getById.mockResolvedValue(customer);
      mockCompanyUserService.hasUnitAccess.mockResolvedValue(false);

      await expect(
        service.getById('c-1', new User({ id: 'u-1', role: UserRole.ATTENDANT })),
      ).rejects.toThrow(ForbiddenException);
    });
  });

  describe('update and delete', () => {
    it('updates customer fields formatting name to title case', async () => {
      const customer = new Customer({
        id: 'c-1',
        company_id: 'comp-1',
        company_unit_id: 'unit-1',
      });
      mockCustomerRepo.getById.mockResolvedValue(customer);
      mockCompanyUserService.hasUnitAccess.mockResolvedValue(true);
      mockCustomerRepo.update.mockResolvedValue(
        new Customer({ ...customer, full_name: 'Novo Nome da Silva' }),
      );

      const res = await service.update(
        'c-1',
        { full_name: 'novo nome da silva' },
        new User({ id: 'u-1', role: UserRole.SUPER_ADMIN }),
      );

      expect(mockCustomerRepo.update).toHaveBeenCalledWith('c-1', {
        full_name: 'Novo Nome da Silva',
        updated_by_user_id: 'u-1',
      });
      expect(res.full_name).toBe('Novo Nome da Silva');
    });

    it('soft deletes customer after verifying access', async () => {
      const customer = new Customer({
        id: 'c-1',
        company_id: 'comp-1',
        company_unit_id: 'unit-1',
      });
      mockCustomerRepo.getById.mockResolvedValue(customer);
      mockCompanyUserService.hasUnitAccess.mockResolvedValue(true);
      mockCustomerRepo.softDelete.mockResolvedValue(true);

      await service.delete('c-1', new User({ id: 'u-1', role: UserRole.SUPER_ADMIN }));
      expect(mockCustomerRepo.softDelete).toHaveBeenCalledWith('c-1');
    });
  });
});

