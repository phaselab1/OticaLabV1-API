import { ApiProperty, ApiPropertyOptional } from '@nestjs/swagger';
import { Type } from 'class-transformer';
import { IsInt, IsOptional, Max, Min } from 'class-validator';

export class PaginationParamsDto {
  @ApiPropertyOptional({
    description: 'Número da página, começando em 1.',
    default: 1,
    minimum: 1,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  page?: number = 1;

  @ApiPropertyOptional({
    description: 'Itens por página (máx. 100).',
    default: 20,
    minimum: 1,
    maximum: 100,
  })
  @IsOptional()
  @Type(() => Number)
  @IsInt()
  @Min(1)
  @Max(100)
  page_size?: number = 20;
}

export class PageDto<T> {
  @ApiProperty({ description: 'Itens da página atual.', isArray: true })
  items: T[];

  @ApiProperty({ description: 'Página atual.' })
  page: number;

  @ApiProperty({ description: 'Tamanho de página solicitado.' })
  page_size: number;

  @ApiProperty({
    description:
      'Total de itens ativos (todas as páginas), para calcular quantas páginas há.',
  })
  total: number;

  constructor(items: T[], page: number, pageSize: number, total: number) {
    this.items = items;
    this.page = page;
    this.page_size = pageSize;
    this.total = total;
  }
}

