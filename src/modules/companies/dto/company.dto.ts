import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
  Length,
  Matches,
  MaxLength,
} from 'class-validator';

export class CreateCompanyDto {
  @ApiProperty({ description: 'Razão social ou nome fantasia.' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(255)
  name: string;

  @ApiProperty({
    description: 'CNPJ único (14 dígitos, somente números).',
    example: '12345678000195',
  })
  @IsString()
  @Matches(/^\d{14}$/, { message: 'CNPJ deve conter exatamente 14 dígitos' })
  cnpj: string;

  @ApiProperty({ description: 'Sigla da UF (2 letras).', example: 'SP' })
  @IsString()
  @Length(2, 2)
  state: string;

  @ApiProperty({ description: 'Município.', example: 'São Paulo' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(100)
  city: string;
}

export class UpdateCompanyDto {
  @ApiPropertyOptional({ description: 'Novo nome, se for alterar.' })
  @IsOptional()
  @IsString()
  @MaxLength(255)
  name?: string;

  @ApiPropertyOptional({
    description: 'Novo CNPJ, se for alterar.',
    example: '12345678000195',
  })
  @IsOptional()
  @IsString()
  @Matches(/^\d{14}$/, { message: 'CNPJ deve conter exatamente 14 dígitos' })
  cnpj?: string;

  @ApiPropertyOptional({
    description: 'Nova sigla da UF (2 letras).',
    example: 'SP',
  })
  @IsOptional()
  @IsString()
  @Length(2, 2)
  state?: string;

  @ApiPropertyOptional({ description: 'Novo município.', example: 'São Paulo' })
  @IsOptional()
  @IsString()
  @MaxLength(100)
  city?: string;
}

export class CompanyResponseDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  name: string;

  @ApiProperty()
  cnpj: string;

  @ApiProperty()
  state: string;

  @ApiProperty()
  city: string;

  @ApiProperty()
  created_by_user_id: string;

  @ApiProperty()
  created_at: string;

  @ApiProperty()
  updated_at: string;
}

export class CreateCompanyUnitDto {
  @ApiProperty({ description: 'Nome da filial/unidade.' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(255)
  name: string;

  @ApiProperty({
    description: 'Código identificador interno (único por empresa).',
    example: 'MATRIZ',
  })
  @IsString()
  @IsNotEmpty()
  @MaxLength(50)
  code: string;

  @ApiProperty({
    description: 'CNPJ da filial (14 dígitos).',
    example: '12345678000195',
  })
  @IsString()
  @Matches(/^\d{14}$/, { message: 'CNPJ deve conter exatamente 14 dígitos' })
  cnpj: string;

  @ApiProperty({ description: 'Sigla da UF (2 letras).', example: 'SP' })
  @IsString()
  @Length(2, 2)
  state: string;

  @ApiProperty({ description: 'Município.', example: 'São Paulo' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(100)
  city: string;
}

export class UpdateCompanyUnitDto {
  @ApiPropertyOptional({ description: 'Novo nome da unidade.' })
  @IsOptional()
  @IsString()
  @MaxLength(255)
  name?: string;

  @ApiPropertyOptional({ description: 'Novo código da unidade.' })
  @IsOptional()
  @IsString()
  @MaxLength(50)
  code?: string;

  @ApiPropertyOptional({ description: 'Novo CNPJ.' })
  @IsOptional()
  @IsString()
  @Matches(/^\d{14}$/, { message: 'CNPJ deve conter exatamente 14 dígitos' })
  cnpj?: string;

  @ApiPropertyOptional({ description: 'Nova UF.' })
  @IsOptional()
  @IsString()
  @Length(2, 2)
  state?: string;

  @ApiPropertyOptional({ description: 'Novo município.' })
  @IsOptional()
  @IsString()
  @MaxLength(100)
  city?: string;
}

export class CompanyUnitResponseDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  company_id: string;

  @ApiProperty()
  name: string;

  @ApiProperty()
  code: string;

  @ApiProperty()
  cnpj: string;

  @ApiProperty()
  state: string;

  @ApiProperty()
  city: string;

  @ApiProperty()
  created_by_user_id: string;

  @ApiProperty()
  created_at: string;

  @ApiProperty()
  updated_at: string;
}

export class CompanyUserGrantDto {
  @ApiProperty({ description: 'UUID do usuário que receberá o acesso.' })
  @IsUUID()
  user_id: string;

  @ApiPropertyOptional({
    description:
      'UUID da unidade. Se omitido/null, concede acesso à EMPRESA INTEIRA.',
  })
  @IsOptional()
  @IsUUID()
  unit_id?: string | null;
}

export class CompanyUserLinkResponseDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  company_id: string;

  @ApiProperty()
  user_id: string;

  @ApiProperty({ nullable: true })
  unit_id: string | null;

  @ApiProperty()
  granted_by_user_id: string;

  @ApiProperty()
  created_at: string;

  @ApiProperty()
  updated_at: string;
}

