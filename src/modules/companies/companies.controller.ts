import {
  Body,
  Controller,
  Delete,
  Get,
  HttpCode,
  HttpStatus,
  Param,
  Post,
  Put,
  Query,
  UseGuards,
} from '@nestjs/common';
import {
  ApiBearerAuth,
  ApiOperation,
  ApiResponse,
  ApiTags,
} from '@nestjs/swagger';
import { PageDto, PaginationParamsDto } from '@/common/dto/pagination.dto';
import { UserRole } from '@/common/enums';
import { CurrentUser } from '@/modules/auth/decorators/current-user.decorator';
import { Roles } from '@/modules/auth/decorators/roles.decorator';
import { JwtAuthGuard } from '@/modules/auth/guards/jwt-auth.guard';
import { RolesGuard } from '@/modules/auth/guards/roles.guard';
import { User } from '@/modules/users/entities/user.entity';
import {
  CompaniesService,
  CompanyUnitsService,
  CompanyUserService,
} from './companies.service';
import {
  CompanyResponseDto,
  CompanyUnitResponseDto,
  CompanyUserGrantDto,
  CompanyUserLinkResponseDto,
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

@ApiTags('companies')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard, RolesGuard)
@Controller('companies')
export class CompaniesController {
  constructor(
    private readonly companiesService: CompaniesService,
    private readonly companyUnitsService: CompanyUnitsService,
    private readonly companyUserService: CompanyUserService,
  ) {}

  // --- Companies Endpoints ---

  @Post()
  @Roles(UserRole.SUPER_ADMIN)
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({ summary: 'Criar empresa' })
  @ApiResponse({ status: 201, type: CompanyResponseDto })
  async createCompany(
    @Body() body: CreateCompanyDto,
    @CurrentUser() currentUser: User,
  ): Promise<Company> {
    return this.companiesService.create(body, currentUser);
  }

  @Get()
  @ApiOperation({ summary: 'Listar empresas' })
  @ApiResponse({ status: 200, type: PageDto<CompanyResponseDto> })
  async listCompanies(
    @CurrentUser() currentUser: User,
    @Query() query: PaginationParamsDto,
  ): Promise<PageDto<Company>> {
    return this.companiesService.getAll(
      currentUser,
      query.page || 1,
      query.page_size || 20,
    );
  }

  @Get(':id')
  @ApiOperation({ summary: 'Buscar empresa por ID' })
  @ApiResponse({ status: 200, type: CompanyResponseDto })
  async getCompany(
    @Param('id') id: string,
    @CurrentUser() currentUser: User,
  ): Promise<Company> {
    return this.companiesService.getById(id, currentUser);
  }

  @Put(':id')
  @Roles(UserRole.SUPER_ADMIN)
  @ApiOperation({ summary: 'Atualizar empresa' })
  @ApiResponse({ status: 200, type: CompanyResponseDto })
  async updateCompany(
    @Param('id') id: string,
    @Body() body: UpdateCompanyDto,
  ): Promise<Company> {
    return this.companiesService.update(id, body);
  }

  @Delete(':id')
  @Roles(UserRole.SUPER_ADMIN)
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Excluir empresa' })
  async deleteCompany(@Param('id') id: string): Promise<void> {
    return this.companiesService.delete(id);
  }

  // --- Company Units Endpoints ---

  @Post(':company_id/units')
  @Roles(UserRole.SUPER_ADMIN)
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({ summary: 'Criar unidade' })
  @ApiResponse({ status: 201, type: CompanyUnitResponseDto })
  async createUnit(
    @Param('company_id') companyId: string,
    @Body() body: CreateCompanyUnitDto,
    @CurrentUser() currentUser: User,
  ): Promise<CompanyUnit> {
    return this.companyUnitsService.create(companyId, body, currentUser);
  }

  @Get(':company_id/units')
  @ApiOperation({ summary: 'Listar unidades de uma empresa' })
  @ApiResponse({ status: 200, type: PageDto<CompanyUnitResponseDto> })
  async listUnits(
    @Param('company_id') companyId: string,
    @CurrentUser() currentUser: User,
    @Query() query: PaginationParamsDto,
  ): Promise<PageDto<CompanyUnit>> {
    return this.companyUnitsService.getAll(
      companyId,
      currentUser,
      query.page || 1,
      query.page_size || 20,
    );
  }

  @Get(':company_id/units/:unit_id')
  @ApiOperation({ summary: 'Buscar unidade por ID' })
  @ApiResponse({ status: 200, type: CompanyUnitResponseDto })
  async getUnit(
    @Param('unit_id') unitId: string,
    @CurrentUser() currentUser: User,
  ): Promise<CompanyUnit> {
    return this.companyUnitsService.getById(unitId, currentUser);
  }

  @Put(':company_id/units/:unit_id')
  @ApiOperation({ summary: 'Atualizar unidade' })
  @ApiResponse({ status: 200, type: CompanyUnitResponseDto })
  async updateUnit(
    @Param('unit_id') unitId: string,
    @Body() body: UpdateCompanyUnitDto,
    @CurrentUser() currentUser: User,
  ): Promise<CompanyUnit> {
    return this.companyUnitsService.update(unitId, body, currentUser);
  }

  @Delete(':company_id/units/:unit_id')
  @Roles(UserRole.SUPER_ADMIN)
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Excluir unidade' })
  async deleteUnit(@Param('unit_id') unitId: string): Promise<void> {
    return this.companyUnitsService.delete(unitId);
  }

  // --- Company Users (Access Grants) Endpoints ---

  @Post(':company_id/users')
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({ summary: 'Conceder acesso a um usuário' })
  @ApiResponse({ status: 201, type: CompanyUserLinkResponseDto })
  async grantAccess(
    @Param('company_id') companyId: string,
    @Body() body: CompanyUserGrantDto,
    @CurrentUser() currentUser: User,
  ): Promise<CompanyUserLink> {
    return this.companyUserService.grant(companyId, body, currentUser);
  }

  @Get(':company_id/users')
  @ApiOperation({ summary: 'Listar acessos concedidos numa empresa' })
  @ApiResponse({ status: 200, type: PageDto<CompanyUserLinkResponseDto> })
  async listAccess(
    @Param('company_id') companyId: string,
    @CurrentUser() currentUser: User,
    @Query() query: PaginationParamsDto,
  ): Promise<PageDto<CompanyUserLink>> {
    return this.companyUserService.getAllForCompany(
      companyId,
      currentUser,
      query.page || 1,
      query.page_size || 20,
    );
  }

  @Delete(':company_id/users/:link_id')
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Revogar acesso de um usuário' })
  async revokeAccess(
    @Param('link_id') linkId: string,
    @CurrentUser() currentUser: User,
  ): Promise<void> {
    return this.companyUserService.revoke(linkId, currentUser);
  }
}

