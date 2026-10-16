import { Body, Controller, HttpCode, Param, ParseUUIDPipe, Post, Put, UseGuards } from '@nestjs/common';
import { ApiBearerAuth, ApiTags } from '@nestjs/swagger';
import { UserRole } from '@/common/enums';
import { Roles } from '@/modules/auth/decorators/roles.decorator';
import { JwtAuthGuard } from '@/modules/auth/guards/jwt-auth.guard';
import { RolesGuard } from '@/modules/auth/guards/roles.guard';
import { UpsertKommoIntegrationDto } from './dto/kommo-integration.dto';
import { KommoAdminService } from './kommo-admin.service';

@ApiTags('Kommo')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard, RolesGuard)
@Roles(UserRole.SUPER_ADMIN)
@Controller('companies/:companyId/kommo-integration')
export class KommoAdminController {
  constructor(private readonly service: KommoAdminService) {}

  @Put()
  upsert(
    @Param('companyId', ParseUUIDPipe) companyId: string,
    @Body() dto: UpsertKommoIntegrationDto,
  ) {
    return this.service.upsert(companyId, dto);
  }

  @Post('rotate-token')
  @HttpCode(200)
  rotate(@Param('companyId', ParseUUIDPipe) companyId: string) {
    return this.service.rotateToken(companyId);
  }
}
