import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { IsInt, IsOptional, IsString, IsUUID, Matches, MinLength } from 'class-validator';

export class UpsertKommoIntegrationDto {
  @ApiProperty()
  @IsUUID()
  company_unit_id: string;

  @ApiProperty({ description: 'Usuário técnico com acesso à unidade' })
  @IsUUID()
  service_user_id: string;

  @ApiProperty({ example: 'oticaszyros' })
  @Matches(/^[a-z0-9-]+$/)
  subdomain: string;

  @ApiPropertyOptional({ description: 'Long-lived token com escopo de escrita; obrigatório na criação' })
  @IsOptional()
  @IsString()
  @MinLength(20)
  access_token?: string;

  @ApiProperty({ example: 14505231 })
  @IsInt()
  pipeline_id: number;

  @ApiProperty({ example: 112039795 })
  @IsInt()
  scheduled_status_id: number;

  @ApiProperty({ example: 614091 })
  @IsInt()
  date_field_id: number;

  @ApiProperty({ example: 614093 })
  @IsInt()
  time_field_id: number;

  @ApiPropertyOptional({ example: 566124 })
  @IsOptional()
  @IsInt()
  referral_field_id?: number;

  @ApiProperty({ example: 268220 })
  @IsInt()
  phone_field_id: number;
}
