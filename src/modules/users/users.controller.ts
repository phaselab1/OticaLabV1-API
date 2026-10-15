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
import {
  CreateUserDto,
  UpdateUserDto,
  UserResponseDto,
} from './dto/user.dto';
import { User } from './entities/user.entity';
import { UsersService } from './users.service';

@ApiTags('users')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard, RolesGuard)
@Controller('users')
export class UsersController {
  constructor(private readonly usersService: UsersService) {}

  @Post()
  @Roles(UserRole.SUPER_ADMIN)
  @HttpCode(HttpStatus.CREATED)
  @ApiOperation({ summary: 'Criar usuário' })
  @ApiResponse({
    status: 201,
    description: 'Usuário criado com sucesso.',
    type: UserResponseDto,
  })
  @ApiResponse({ status: 401, description: 'Token ausente ou inválido.' })
  @ApiResponse({ status: 403, description: 'Requer role `super_admin`.' })
  @ApiResponse({
    status: 409,
    description: 'Já existe um usuário ativo com esse e-mail.',
  })
  @ApiResponse({
    status: 422,
    description: 'Dados inválidos (ex: senha com menos de 8 caracteres).',
  })
  async create(@Body() body: CreateUserDto): Promise<User> {
    return this.usersService.create(body);
  }

  @Get()
  @ApiOperation({ summary: 'Listar usuários' })
  @ApiResponse({
    status: 200,
    description: 'Lista paginada de usuários.',
    type: PageDto<UserResponseDto>,
  })
  @ApiResponse({ status: 401, description: 'Token ausente ou inválido.' })
  async getAll(
    @CurrentUser() currentUser: User,
    @Query() query: PaginationParamsDto,
  ): Promise<PageDto<User>> {
    return this.usersService.getAll(
      currentUser,
      query.page || 1,
      query.page_size || 20,
    );
  }

  @Get(':id')
  @ApiOperation({ summary: 'Buscar usuário por ID' })
  @ApiResponse({
    status: 200,
    description: 'Usuário encontrado.',
    type: UserResponseDto,
  })
  @ApiResponse({ status: 401, description: 'Token ausente ou inválido.' })
  @ApiResponse({
    status: 403,
    description:
      'Usuário não compartilha vínculo de empresa com o usuário buscado.',
  })
  @ApiResponse({
    status: 404,
    description: 'Usuário não encontrado (ou soft-deletado).',
  })
  async getById(
    @Param('id') id: string,
    @CurrentUser() currentUser: User,
  ): Promise<User> {
    return this.usersService.getById(id, currentUser);
  }

  @Put(':id')
  @Roles(UserRole.SUPER_ADMIN)
  @ApiOperation({ summary: 'Atualizar usuário' })
  @ApiResponse({
    status: 200,
    description: 'Usuário atualizado com sucesso.',
    type: UserResponseDto,
  })
  @ApiResponse({ status: 401, description: 'Token ausente ou inválido.' })
  @ApiResponse({ status: 403, description: 'Requer role `super_admin`.' })
  @ApiResponse({
    status: 404,
    description: 'Usuário não encontrado (ou soft-deletado).',
  })
  @ApiResponse({
    status: 409,
    description: 'Já existe um usuário ativo com o novo e-mail informado.',
  })
  async update(
    @Param('id') id: string,
    @Body() body: UpdateUserDto,
  ): Promise<User> {
    return this.usersService.update(id, body);
  }

  @Delete(':id')
  @Roles(UserRole.SUPER_ADMIN)
  @HttpCode(HttpStatus.NO_CONTENT)
  @ApiOperation({ summary: 'Excluir usuário' })
  @ApiResponse({ status: 204, description: 'Usuário removido com sucesso.' })
  @ApiResponse({ status: 401, description: 'Token ausente ou inválido.' })
  @ApiResponse({ status: 403, description: 'Requer role `super_admin`.' })
  @ApiResponse({
    status: 404,
    description: 'Usuário não encontrado (ou já soft-deletado).',
  })
  async delete(@Param('id') id: string): Promise<void> {
    return this.usersService.delete(id);
  }
}

