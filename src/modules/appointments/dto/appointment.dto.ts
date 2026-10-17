import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import {
  IsDateString,
  IsEnum,
  IsNotEmpty,
  IsOptional,
  IsString,
  IsUUID,
  Matches,
  MaxLength,
} from 'class-validator';
import { AppointmentStatus } from '@/common/enums';

export class CreateAppointmentDto {
  @ApiPropertyOptional({
    description: 'UUID da empresa. Preenchido automaticamente para não-super_admin.',
  })
  @IsOptional()
  @IsUUID()
  company_id?: string | null;

  @ApiPropertyOptional({
    description: 'UUID da unidade. Preenchido automaticamente quando não ambíguo.',
  })
  @IsOptional()
  @IsUUID()
  company_unit_id?: string | null;

  @ApiProperty({ description: 'Nome completo de quem está marcando (lead).' })
  @IsString()
  @IsNotEmpty()
  @MaxLength(255)
  lead_full_name: string;

  @ApiProperty({
    description: 'Telefone do lead com DDD.',
    example: '11987654321',
  })
  @IsString()
  @Matches(/^\d{10,11}$/, {
    message: 'Telefone deve conter 10 ou 11 dígitos com DDD',
  })
  lead_phone: string;

  @ApiProperty({
    description: 'Data e hora do agendamento (ISO8601 com timezone).',
    example: '2026-10-15T14:30:00Z',
  })
  @IsDateString()
  scheduled_at: string;

  @ApiPropertyOptional({ description: 'Observações do agendamento.' })
  @IsOptional()
  @IsString()
  notes?: string | null;
}

export class UpdateAppointmentDto {
  @ApiPropertyOptional({ description: 'Data e hora do agendamento.' })
  @IsOptional()
  @IsDateString()
  scheduled_at?: string;

  @ApiPropertyOptional({
    description: 'Novo status do agendamento.',
    enum: AppointmentStatus,
  })
  @IsOptional()
  @IsEnum(AppointmentStatus)
  status?: AppointmentStatus;

  @ApiPropertyOptional({ description: 'Observações.' })
  @IsOptional()
  @IsString()
  notes?: string | null;

  @ApiPropertyOptional({
    description:
      'Nome completo do lead (só pode ser alterado se ainda não promovido a cliente).',
  })
  @IsOptional()
  @IsString()
  @MaxLength(255)
  lead_full_name?: string;

  @ApiPropertyOptional({
    description:
      'Telefone do lead (só pode ser alterado se ainda não promovido a cliente).',
  })
  @IsOptional()
  @IsString()
  @Matches(/^\d{10,11}$/, {
    message: 'Telefone deve conter 10 ou 11 dígitos com DDD',
  })
  lead_phone?: string;
}

export class RescheduleAppointmentDto {
  @ApiProperty({
    description: 'Nova data e hora do agendamento.',
    example: '2026-10-16T15:00:00Z',
  })
  @IsDateString()
  scheduled_at: string;

  @ApiPropertyOptional({ description: 'Novas observações.' })
  @IsOptional()
  @IsString()
  notes?: string | null;
}

export class AppointmentResponseDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  company_id: string;

  @ApiProperty()
  company_unit_id: string;

  @ApiProperty()
  lead_full_name: string;

  @ApiProperty()
  lead_phone: string;

  @ApiProperty({ nullable: true })
  customer_id: string | null;

  @ApiProperty()
  created_by_user_id: string;

  @ApiProperty()
  updated_by_user_id: string;

  @ApiProperty()
  scheduled_at: string;

  @ApiProperty({ enum: AppointmentStatus })
  status: AppointmentStatus;

  @ApiProperty({ nullable: true })
  notes: string | null;

  @ApiProperty()
  created_at: string;

  @ApiProperty()
  updated_at: string;
}

export class AppointmentHistoryResponseDto {
  @ApiProperty()
  id: string;

  @ApiProperty()
  appointment_id: string;

  @ApiProperty()
  changed_by_user_id: string;

  @ApiProperty()
  previous_scheduled_at: string;

  @ApiProperty()
  new_scheduled_at: string;

  @ApiProperty({ enum: AppointmentStatus })
  previous_status: AppointmentStatus;

  @ApiProperty({ enum: AppointmentStatus })
  new_status: AppointmentStatus;

  @ApiProperty({ nullable: true })
  notes: string | null;

  @ApiProperty()
  changed_at: string;
}

