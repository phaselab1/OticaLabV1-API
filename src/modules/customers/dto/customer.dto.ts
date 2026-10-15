import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
  Matches,
  MaxLength,
} from 'class-validator';

export class CreateCustomerDto {
  @ApiPropertyOptional({
    description:
      'UUID da empresa. Obrigatório para super_admin; preenchido automaticamente para outros papéis.',
  })
  @IsOptional()
  @IsUUID()
  company_id?: string | null;

  @ApiPropertyOptional({
    description:
      'UUID da unidade. Obrigatório para super_admin/admin; preenchido automaticamente quando não houver ambiguidade.',
  })
  @IsOptional()
  @IsUUID()
  company_unit_id?: string | null;

  @ApiProperty({ description: 'Nome completo do cliente.', example: 'Maria Santos' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(255)
  full_name: string;

  @ApiProperty({
    description: 'Telefone com DDD (somente dígitos).',
    example: '11987654321',
  })
  @IsString()
  @Matches(/^\d{10,11}$/, {
    message: 'Telefone deve conter 10 ou 11 dígitos com DDD',
  })
  phone: string;
}

export class UpdateCustomerDto {
  @ApiPropertyOptional({ description: 'Novo nome completo.' })
  @IsOptional()
  @IsString()
  @MaxLength(255)
  full_name?: string;

  @ApiPropertyOptional({ description: 'Novo telefone com DDD.' })
  @IsOptional()
  @IsString()
  @Matches(/^\d{10,11}$/, {
    message: 'Telefone deve conter 10 ou 11 dígitos com DDD',
  })
  phone?: string;
}

export class CustomerResponseDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  company_id: string;

  @ApiProperty()
  company_unit_id: string;

  @ApiProperty()
  full_name: string;

  @ApiProperty()
  phone: string;

  @ApiProperty()
  created_by_user_id: string;

  @ApiProperty()
  updated_by_user_id: string;

  @ApiProperty()
  created_at: string;

  @ApiProperty()
  updated_at: string;
}

