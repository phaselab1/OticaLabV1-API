import { BadRequestException, ForbiddenException } from '@nestjs/common';
import { UserRole } from '@/common/enums';
import { User } from '@/modules/users/entities/user.entity';
import { CompanyUserService } from './companies.service';
import { CompanyUserLink } from './entities/company.entity';

describe('CompanyUserService - resolveCompanyAndUnit', () => {
  let service: CompanyUserService;
  let mockLinkRepo: any;
  let mockCompanyRepo: any;
  let mockUnitRepo: any;
  let mockUserRepo: any;

  beforeEach(() => {
    mockLinkRepo = {
      getAllForUser: vi.fn(),
    };
    mockCompanyRepo = {};
    mockUnitRepo = {};
    mockUserRepo = {};

    service = new CompanyUserService(
      mockLinkRepo,
      mockCompanyRepo,
      mockUnitRepo,
      mockUserRepo,
    );
  });

  it('super_admin must provide both company_id and company_unit_id', async () => {
    const superAdmin = new User({
      id: 'super-1',
      role: UserRole.SUPER_ADMIN,
    });

    await expect(
      service.resolveCompanyAndUnit(superAdmin, null, 'unit-1'),
    ).rejects.toThrow(BadRequestException);

    await expect(
      service.resolveCompanyAndUnit(superAdmin, 'comp-1', null),
    ).rejects.toThrow(BadRequestException);

    const [comp, unit] = await service.resolveCompanyAndUnit(
      superAdmin,
      'comp-1',
      'unit-1',
    );
    expect(comp).toBe('comp-1');
    expect(unit).toBe('unit-1');
  });

  it('user with single unit access resolves company and unit automatically', async () => {
    const attendant = new User({
      id: 'att-1',
      role: UserRole.ATTENDANT,
    });

    mockLinkRepo.getAllForUser.mockResolvedValue([
      new CompanyUserLink({
        company_id: 'comp-1',
        user_id: 'att-1',
        unit_id: 'unit-1',
      }),
    ]);

    const [comp, unit] = await service.resolveCompanyAndUnit(
      attendant,
      null,
      null,
    );
    expect(comp).toBe('comp-1');
    expect(unit).toBe('unit-1');
  });

  it('user with whole-company access requires specifying unit_id', async () => {
    const admin = new User({
      id: 'admin-1',
      role: UserRole.ADMIN,
    });

    mockLinkRepo.getAllForUser.mockResolvedValue([
      new CompanyUserLink({
        company_id: 'comp-1',
        user_id: 'admin-1',
        unit_id: null,
      }),
    ]);

    await expect(
      service.resolveCompanyAndUnit(admin, null, null),
    ).rejects.toThrow(BadRequestException);
  });

  it('user accessing company without permissions throws ForbiddenException', async () => {
    const attendant = new User({
      id: 'att-1',
      role: UserRole.ATTENDANT,
    });

    mockLinkRepo.getAllForUser.mockResolvedValue([
      new CompanyUserLink({
        company_id: 'comp-1',
        user_id: 'att-1',
        unit_id: 'unit-1',
      }),
    ]);

    await expect(
      service.resolveCompanyAndUnit(attendant, 'comp-2', 'unit-1'),
    ).rejects.toThrow(ForbiddenException);
  });
});

