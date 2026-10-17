import {
  ForbiddenException,
  Injectable,
  NotFoundException,
} from '@nestjs/common';
import { PageDto } from '@/common/dto/pagination.dto';
import { UserRole } from '@/common/enums';
import { formatTitleCase } from '@/common/utils/text.util';
import { CompanyUserService } from '@/modules/companies/companies.service';
import { User } from '@/modules/users/entities/user.entity';
import { CreateCustomerDto, UpdateCustomerDto } from './dto/customer.dto';
import { Customer } from './entities/customer.entity';
import { CustomerRepository } from './repositories/customer.repository';

@Injectable()
export class CustomersService {
  constructor(
    private readonly customerRepository: CustomerRepository,
    private readonly companyUserService: CompanyUserService,
  ) {}

  async create(data: CreateCustomerDto, currentUser: User): Promise<Customer> {
    const [companyId, companyUnitId] =
      await this.companyUserService.resolveCompanyAndUnit(
        currentUser,
        data.company_id,
        data.company_unit_id,
      );

    return this.customerRepository.create({
      company_id: companyId,
      company_unit_id: companyUnitId,
      full_name: formatTitleCase(data.full_name),
      phone: data.phone,
      created_by_user_id: currentUser.id,
      updated_by_user_id: currentUser.id,
    });
  }

  async getAll(
    currentUser: User,
    page: number = 1,
    pageSize: number = 20,
    companyId?: string | null,
    companyUnitId?: string | null,
  ): Promise<PageDto<Customer>> {
    let resolvedCompanyId = companyId;
    let resolvedUnitId = companyUnitId;

    if (currentUser.role !== UserRole.SUPER_ADMIN) {
      [resolvedCompanyId, resolvedUnitId] =
        await this.companyUserService.resolveScopeForList(
          currentUser,
          companyId,
          companyUnitId,
        );
    }

    if (resolvedCompanyId === '__none__') {
      return new PageDto([], page, pageSize, 0);
    }

    const [items, total] = await this.customerRepository.getAll(
      page,
      pageSize,
      resolvedCompanyId,
      resolvedUnitId,
    );
    return new PageDto(items, page, pageSize, total);
  }

  async getById(customerId: string, currentUser: User): Promise<Customer> {
    const customer = await this.customerRepository.getById(customerId);
    if (!customer) {
      throw new NotFoundException(`Customer '${customerId}' not found`);
    }

    if (currentUser.role !== UserRole.SUPER_ADMIN) {
      const hasAccess = await this.companyUserService.hasUnitAccess(
        currentUser,
        customer.company_id,
        customer.company_unit_id,
      );
      if (!hasAccess) {
        throw new ForbiddenException(
          'Você não tem permissão para acessar os clientes desta unidade.',
        );
      }
    }

    return customer;
  }

  async update(
    customerId: string,
    data: UpdateCustomerDto,
    currentUser: User,
  ): Promise<Customer> {
    await this.getById(customerId, currentUser);

    const payload: Partial<Customer> = {
      updated_by_user_id: currentUser.id,
    };
    if (data.full_name !== undefined) {
      payload.full_name = formatTitleCase(data.full_name);
    }
    if (data.phone !== undefined) {
      payload.phone = data.phone;
    }

    const updated = await this.customerRepository.update(customerId, payload);
    if (!updated) {
      throw new NotFoundException(`Customer '${customerId}' not found`);
    }
    return updated;
  }

  async delete(customerId: string, currentUser: User): Promise<void> {
    await this.getById(customerId, currentUser);
    const deleted = await this.customerRepository.softDelete(customerId);
    if (!deleted) {
      throw new NotFoundException(`Customer '${customerId}' not found`);
    }
  }

  // Helper for internal use (appointment lead promotion)
  getCustomerRepository(): CustomerRepository {
    return this.customerRepository;
  }
}

