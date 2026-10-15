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
  ApiQuery,
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
import { CustomersService } from './customers.service';
import {
  CreateCustomerDto,
  CustomerResponseDto,
  UpdateCustomerDto,
} from './dto/customer.dto';
import { Customer } from './entities/customer.entity';

@ApiTags('customers')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard, RolesGuard)
@Controller('customers')
export class CustomersController {
  constructor(private readonly customersService: CustomersService) {}

  @Post()
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({ summary: 'Cadastrar cliente' })
  @ApiResponse({ status: 201, type: CustomerResponseDto })
  @ApiResponse({ status: 400, description: 'Erro de vínculo ou ambiguidade.' })
  @ApiResponse({ status: 401, description: 'Token ausente ou inválido.' })
  @ApiResponse({ status: 403, description: 'Acesso negado à unidade.' })
  @ApiResponse({ status: 409, description: 'Cliente duplicado.' })
  async create(
    @Body() body: CreateCustomerDto,
    @CurrentUser() currentUser: User,
  ): Promise<Customer> {
    return this.customersService.create(body, currentUser);
  }

  @Get()
  @ApiOperation({ summary: 'Listar clientes' })
  @ApiQuery({ name: 'company_id', required: false, type: String })
  @ApiQuery({ name: 'company_unit_id', required: false, type: String })
  @ApiResponse({ status: 200, type: PageDto<CustomerResponseDto> })
  async getAll(
    @CurrentUser() currentUser: User,
    @Query() query: PaginationParamsDto,
    @Query('company_id') companyId?: string,
    @Query('company_unit_id') companyUnitId?: string,
  ): Promise<PageDto<Customer>> {
    return this.customersService.getAll(
      currentUser,
      query.page || 1,
      query.page_size || 20,
      companyId,
      companyUnitId,
    );
  }

  @Get(':id')
  @ApiOperation({ summary: 'Buscar cliente por ID' })
  @ApiResponse({ status: 200, type: CustomerResponseDto })
  async getById(
    @Param('id') id: string,
    @CurrentUser() currentUser: User,
  ): Promise<Customer> {
    return this.customersService.getById(id, currentUser);
  }

  @Put(':id')
  @ApiOperation({ summary: 'Atualizar cliente' })
  @ApiResponse({ status: 200, type: CustomerResponseDto })
  async update(
    @Param('id') id: string,
    @Body() body: UpdateCustomerDto,
    @CurrentUser() currentUser: User,
  ): Promise<Customer> {
    return this.customersService.update(id, body, currentUser);
  }

  @Delete(':id')
  @Roles(UserRole.SUPER_ADMIN, UserRole.ADMIN, UserRole.MANAGER)
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Excluir cliente' })
  @ApiResponse({ status: 204, description: 'Removido com sucesso.' })
  @ApiResponse({ status: 403, description: 'Attendant não pode excluir.' })
  async delete(
    @Param('id') id: string,
    @CurrentUser() currentUser: User,
  ): Promise<void> {
    return this.customersService.delete(id, currentUser);
  }
}

