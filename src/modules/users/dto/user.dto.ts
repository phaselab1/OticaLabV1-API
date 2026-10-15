import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsEmail,
  IsEnum,
  IsNotEmpty,
  IsOptional,
  IsString,
  MaxLength,
  MinLength,
} from 'class-validator';
import { UserRole } from '@/common/enums';

export class CreateUserDto {
  @ApiProperty({
    description: 'Nome completo do usuário.',
    example: 'Ana Silva',
    maxLength: 255,
  })
  @IsString()
  @IsNotEmpty()
  @MaxLength(255)
  full_name: string;

  @ApiProperty({
    description: 'E-mail único — vira o login.',
    example: 'ana@oticalab.com',
    maxLength: 255,
  })
  @IsEmail()
  @MaxLength(255)
  email: string;

  @ApiProperty({
    description:
      'Senha em texto plano (8 a 72 caracteres — limite do bcrypt) — nunca armazenada como tal.',
    minLength: 8,
    maxLength: 72,
  })
  @IsString()
  @MinLength(8)
  @MaxLength(72)
  password: string;

  @ApiPropertyOptional({
    description:
      'Papel do usuário. `super_admin` tem acesso global; `admin` acessa uma empresa inteira; `manager` gerencia uma unidade específica; `attendant` opera na empresa/unidade(s) às quais foi vinculado via `company_users`.',
    enum: UserRole,
    default: UserRole.ATTENDANT,
  })
  @IsOptional()
  @IsEnum(UserRole)
  role?: UserRole = UserRole.ATTENDANT;
}

export class UpdateUserDto {
  @ApiPropertyOptional({
    description: 'Novo nome completo, se for alterar.',
    maxLength: 255,
  })
  @IsOptional()
  @IsString()
  @MaxLength(255)
  full_name?: string;

  @ApiPropertyOptional({
    description: 'Novo e-mail, se for alterar.',
    maxLength: 255,
  })
  @IsOptional()
  @IsEmail()
  @MaxLength(255)
  email?: string;

  @ApiPropertyOptional({
    description: 'Novo papel, se for alterar.',
    enum: UserRole,
  })
  @IsOptional()
  @IsEnum(UserRole)
  role?: UserRole;
}

export class UserResponseDto {
  @ApiProperty({ description: 'UUID do usuário.' })
  id: string;

  @ApiProperty({ description: 'Nome completo do usuário.' })
  full_name: string;

  @ApiProperty({ description: 'E-mail único.' })
  email: string;

  @ApiProperty({ enum: UserRole, description: 'Papel do usuário.' })
  role: UserRole;

  @ApiProperty({ description: 'Data de criação em ISO8601.' })
  created_at: string;

  @ApiProperty({ description: 'Data de atualização em ISO8601.' })
  updated_at: string;
}

