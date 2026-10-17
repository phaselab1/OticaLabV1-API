import {
  BadRequestException,
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { PageDto } from '@/common/dto/pagination.dto';
import { UserRole } from '@/common/enums';
import { User } from '@/modules/users/entities/user.entity';
import { UserRepository } from '@/modules/users/repositories/user.repository';
import {
  CompanyUserGrantDto,
  CreateCompanyDto,
  CreateCompanyUnitDto,
  UpdateCompanyDto,
  UpdateCompanyUnitDto,
} from './dto/company.dto';
import {
  Company,
  CompanyUnit,
  CompanyUserLink,
} from './entities/company.entity';
import {
  CompanyRepository,
  CompanyUnitRepository,
  CompanyUserRepository,
} from './repositories/company.repository';

@Injectable()
export class CompaniesService {
  constructor(
    private readonly companyRepo: CompanyRepository,
    private readonly companyUserRepo: CompanyUserRepository,
  ) {}

  async create(data: CreateCompanyDto, currentUser: User): Promise<Company> {
    return this.companyRepo.create({
      name: data.name,
      cnpj: data.cnpj,
      state: data.state.toUpperCase(),
      city: data.city,
      created_by_user_id: currentUser.id,
    });
  }

  async getAll(
    currentUser: User,
    page: number = 1,
    pageSize: number = 20,
  ): Promise<PageDto<Company>> {
    let companyIds: string[] | undefined;
    if (currentUser.role !== UserRole.SUPER_ADMIN) {
      const links = await this.companyUserRepo.getAllForUser(currentUser.id);
      companyIds = Array.from(new Set(links.map((l) => l.company_id)));
      if (companyIds.length === 0) {
        return new PageDto([], page, pageSize, 0);
      }
    }

    const [items, total] = await this.companyRepo.getAll(
      page,
      pageSize,
      companyIds,
    );
    return new PageDto(items, page, pageSize, total);
  }

  async getById(id: string, currentUser: User): Promise<Company> {
    const company = await this.companyRepo.getById(id);
    if (!company) {
      throw new NotFoundException(`Company '${id}' not found`);
    }

    if (currentUser.role !== UserRole.SUPER_ADMIN) {
      const links = await this.companyUserRepo.getAllForUser(currentUser.id);
      const hasAccess = links.some((l) => l.company_id === id);
      if (!hasAccess) {
        throw new NotFoundException(`Company '${id}' not found`);
      }
    }

    return company;
  }

  async update(id: string, data: UpdateCompanyDto): Promise<Company> {
    const updatePayload: Partial<Company> = {};
    if (data.name !== undefined) updatePayload.name = data.name;
    if (data.cnpj !== undefined) updatePayload.cnpj = data.cnpj;
    if (data.state !== undefined)
      updatePayload.state = data.state.toUpperCase();
    if (data.city !== undefined) updatePayload.city = data.city;

    const updated = await this.companyRepo.update(id, updatePayload);
    if (!updated) {
      throw new NotFoundException(`Company '${id}' not found`);
    }
    return updated;
  }

  async delete(id: string): Promise<void> {
    const deleted = await this.companyRepo.softDelete(id);
    if (!deleted) {
      throw new NotFoundException(`Company '${id}' not found`);
    }
  }
}

@Injectable()
export class CompanyUnitsService {
  constructor(
    private readonly unitRepo: CompanyUnitRepository,
    private readonly companyRepo: CompanyRepository,
    private readonly companyUserRepo: CompanyUserRepository,
  ) {}

  async create(
    companyId: string,
    data: CreateCompanyUnitDto,
    currentUser: User,
  ): Promise<CompanyUnit> {
    const company = await this.companyRepo.getById(companyId);
    if (!company) {
      throw new NotFoundException(`Company '${companyId}' not found`);
    }

    return this.unitRepo.create({
      company_id: companyId,
      name: data.name,
      code: data.code,
      cnpj: data.cnpj,
      state: data.state.toUpperCase(),
      city: data.city,
      created_by_user_id: currentUser.id,
    });
  }

  async getAll(
    companyId: string,
    currentUser: User,
    page: number = 1,
    pageSize: number = 20,
  ): Promise<PageDto<CompanyUnit>> {
    if (currentUser.role !== UserRole.SUPER_ADMIN) {
      const links = await this.companyUserRepo.getAllForUser(currentUser.id);
      const hasAccess = links.some((l) => l.company_id === companyId);
      if (!hasAccess) {
        throw new ForbiddenException(
          `No access to company units of '${companyId}'`,
        );
      }
    }

    const [items, total] = await this.unitRepo.getAll(
      companyId,
      page,
      pageSize,
    );
    return new PageDto(items, page, pageSize, total);
  }

  async getById(unitId: string, currentUser: User): Promise<CompanyUnit> {
    const unit = await this.unitRepo.getById(unitId);
    if (!unit) {
      throw new NotFoundException(`Unit '${unitId}' not found`);
    }

    if (currentUser.role !== UserRole.SUPER_ADMIN) {
      const links = await this.companyUserRepo.getAllForUser(currentUser.id);
      const hasAccess = links.some(
        (l) =>
          l.company_id === unit.company_id &&
          (l.unit_id === null || l.unit_id === unitId),
      );
      if (!hasAccess) {
        throw new NotFoundException(`Unit '${unitId}' not found`);
      }
    }

    return unit;
  }

  async update(
    unitId: string,
    data: UpdateCompanyUnitDto,
    currentUser: User,
  ): Promise<CompanyUnit> {
    const unit = await this.unitRepo.getById(unitId);
    if (!unit) {
      throw new NotFoundException(`Unit '${unitId}' not found`);
    }

    if (currentUser.role !== UserRole.SUPER_ADMIN) {
      const links = await this.companyUserRepo.getAllForUser(currentUser.id);
      const isCompanyAdmin = links.some(
        (l) => l.company_id === unit.company_id && l.unit_id === null,
      );
      if (!isCompanyAdmin) {
        throw new ForbiddenException('Insufficient access to manage this unit');
      }
    }

    const payload: Partial<CompanyUnit> = {};
    if (data.name !== undefined) payload.name = data.name;
    if (data.code !== undefined) payload.code = data.code;
    if (data.cnpj !== undefined) payload.cnpj = data.cnpj;
    if (data.state !== undefined) payload.state = data.state.toUpperCase();
    if (data.city !== undefined) payload.city = data.city;

    const updated = await this.unitRepo.update(unitId, payload);
    if (!updated) {
      throw new NotFoundException(`Unit '${unitId}' not found`);
    }
    return updated;
  }

  async delete(unitId: string): Promise<void> {
    const deleted = await this.unitRepo.softDelete(unitId);
    if (!deleted) {
      throw new NotFoundException(`Unit '${unitId}' not found`);
    }
  }
}

@Injectable()
export class CompanyUserService {
  constructor(
    private readonly linkRepo: CompanyUserRepository,
    private readonly companyRepo: CompanyRepository,
    private readonly unitRepo: CompanyUnitRepository,
    private readonly userRepo: UserRepository,
  ) {}

  async hasCompanyAdminAccess(
    user: User,
    companyId: string,
  ): Promise<boolean> {
    if (user.role === UserRole.SUPER_ADMIN) return true;
    const links = await this.linkRepo.getAllForUser(user.id);
    return links.some((l) => l.company_id === companyId && l.unit_id === null);
  }

  async hasUnitAccess(
    user: User,
    companyId: string,
    unitId: string,
  ): Promise<boolean> {
    if (user.role === UserRole.SUPER_ADMIN) return true;
    const links = await this.linkRepo.getAllForUser(user.id);
    return links.some(
      (l) =>
        l.company_id === companyId &&
        (l.unit_id === null || l.unit_id === unitId),
    );
  }

  async grant(
    companyId: string,
    data: CompanyUserGrantDto,
    currentUser: User,
  ): Promise<CompanyUserLink> {
    if (!(await this.hasCompanyAdminAccess(currentUser, companyId))) {
      throw new ForbiddenException('Insufficient access to manage this company');
    }

    const company = await this.companyRepo.getById(companyId);
    if (!company) {
      throw new NotFoundException(`Company '${companyId}' not found`);
    }

    const targetUser = await this.userRepo.getById(data.user_id);
    if (!targetUser) {
      throw new NotFoundException(`User '${data.user_id}' not found`);
    }

    if (targetUser.role === UserRole.MANAGER && !data.unit_id) {
      throw new BadRequestException(
        `User ${data.user_id} has role 'manager' and requires a specific unit_id`,
      );
    }

    if (data.unit_id) {
      const unit = await this.unitRepo.getById(data.unit_id);
      if (!unit || unit.company_id !== companyId) {
        throw new NotFoundException(`Unit '${data.unit_id}' not found`);
      }
    }

    return this.linkRepo.create({
      company_id: companyId,
      user_id: data.user_id,
      unit_id: data.unit_id || null,
      granted_by_user_id: currentUser.id,
    });
  }

  async getAllForCompany(
    companyId: string,
    currentUser: User,
    page: number = 1,
    pageSize: number = 20,
  ): Promise<PageDto<CompanyUserLink>> {
    if (!(await this.hasCompanyAdminAccess(currentUser, companyId))) {
      throw new ForbiddenException('Insufficient access to manage this company');
    }

    const [items, total] = await this.linkRepo.getAllForCompany(
      companyId,
      page,
      pageSize,
    );
    return new PageDto(items, page, pageSize, total);
  }

  async revoke(linkId: string, currentUser: User): Promise<void> {
    const link = await this.linkRepo.getById(linkId);
    if (!link) {
      throw new NotFoundException(`Link '${linkId}' not found`);
    }

    if (!(await this.hasCompanyAdminAccess(currentUser, link.company_id))) {
      throw new ForbiddenException('Insufficient access to manage this company');
    }

    await this.linkRepo.softDelete(linkId);
  }

  async resolveCompanyAndUnit(
    currentUser: User,
    companyId?: string | null,
    unitId?: string | null,
  ): Promise<[string, string]> {
    if (currentUser.role === UserRole.SUPER_ADMIN) {
      if (!companyId || !unitId) {
        throw new BadRequestException(
          'super_admin must provide both company_id and company_unit_id',
        );
      }
      return [companyId, unitId];
    }

    const links = await this.linkRepo.getAllForUser(currentUser.id);

    let resolvedCompanyId = companyId;
    if (!resolvedCompanyId) {
      const companyIds = Array.from(new Set(links.map((l) => l.company_id)));
      if (companyIds.length !== 1) {
        throw new BadRequestException(
          'company_id is required (user has access to zero or multiple companies)',
        );
      }
      resolvedCompanyId = companyIds[0];
    } else if (!links.some((l) => l.company_id === resolvedCompanyId)) {
      throw new ForbiddenException(`No access to company ${resolvedCompanyId}`);
    }

    let resolvedUnitId = unitId;
    if (!resolvedUnitId) {
      const companyLinks = links.filter(
        (l) => l.company_id === resolvedCompanyId,
      );
      const hasWholeCompany = companyLinks.some((l) => l.unit_id === null);
      if (hasWholeCompany) {
        throw new BadRequestException(
          'company_unit_id is required (user has whole-company access)',
        );
      }

      const unitIds = Array.from(
        new Set(companyLinks.map((l) => l.unit_id).filter(Boolean)),
      );
      if (unitIds.length !== 1) {
        throw new BadRequestException(
          'company_unit_id is required (user has access to zero or multiple units)',
        );
      }
      resolvedUnitId = unitIds[0] as string;
    } else if (
      !(await this.hasUnitAccess(
        currentUser,
        resolvedCompanyId,
        resolvedUnitId,
      ))
    ) {
      throw new ForbiddenException(
        `No access to unit ${resolvedUnitId} of company ${resolvedCompanyId}`,
      );
    }

    return [resolvedCompanyId, resolvedUnitId];
  }

  async resolveScopeForList(
    currentUser: User,
    companyId?: string | null,
    unitId?: string | null,
  ): Promise<[string | null, string | null]> {
    if (currentUser.role === UserRole.SUPER_ADMIN) {
      return [companyId || null, unitId || null];
    }

    const links = await this.linkRepo.getAllForUser(currentUser.id);
    if (!links || links.length === 0) {
      return ['__none__', '__none__'];
    }

    let resolvedCompanyId = companyId;
    if (!resolvedCompanyId) {
      const companyIds = Array.from(new Set(links.map((l) => l.company_id)));
      if (companyIds.length === 1) {
        resolvedCompanyId = companyIds[0];
      } else if (companyIds.length > 1) {
        resolvedCompanyId = companyIds[0];
      }
    } else if (!links.some((l) => l.company_id === resolvedCompanyId)) {
      throw new ForbiddenException(`No access to company ${resolvedCompanyId}`);
    }

    if (unitId) {
      if (
        !(await this.hasUnitAccess(
          currentUser,
          resolvedCompanyId as string,
          unitId,
        ))
      ) {
        throw new ForbiddenException(
          `No access to unit ${unitId} of company ${resolvedCompanyId}`,
        );
      }
      return [resolvedCompanyId || null, unitId];
    }

    const companyLinks = resolvedCompanyId
      ? links.filter((l) => l.company_id === resolvedCompanyId)
      : links;

    const hasWholeCompanyAccess = companyLinks.some((l) => l.unit_id === null);
    if (hasWholeCompanyAccess) {
      return [resolvedCompanyId || null, null];
    }

    const unitIds = Array.from(
      new Set(companyLinks.map((l) => l.unit_id).filter(Boolean)),
    );
    if (unitIds.length === 1) {
      return [resolvedCompanyId || null, unitIds[0] as string];
    }

    return [resolvedCompanyId || null, null];
  }
}

