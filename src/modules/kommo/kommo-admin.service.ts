import { BadRequestException, Injectable, NotFoundException } from '@nestjs/common';
import { UpsertKommoIntegrationDto } from './dto/kommo-integration.dto';
import { KommoCryptoService } from './kommo-crypto.service';
import { KommoIntegrationRepository } from './repositories/kommo-integration.repository';

const WEBHOOK_PREFIX = '/kommo/agendamento/';

@Injectable()
export class KommoAdminService {
  constructor(
    private readonly repo: KommoIntegrationRepository,
    private readonly crypto: KommoCryptoService,
  ) {}

  async upsert(
    companyId: string,
    dto: UpsertKommoIntegrationDto,
  ): Promise<{ id: string; webhook_path?: string }> {
    const { access_token, ...fields } = dto;
    const config = { ...fields, referral_field_id: fields.referral_field_id ?? null };
    const existing = await this.repo.findActiveByCompany(companyId);

    if (existing) {
      const updated = await this.repo.update(existing.id, {
        ...config,
        ...(access_token ? { access_token_encrypted: this.crypto.encrypt(access_token) } : {}),
      });
      return { id: updated.id };
    }

    if (!access_token) {
      throw new BadRequestException('access_token é obrigatório ao criar a integração');
    }
    const tenantToken = this.crypto.generateTenantToken();
    const created = await this.repo.create({
      ...config,
      company_id: companyId,
      access_token_encrypted: this.crypto.encrypt(access_token),
      tenant_token_hash: this.crypto.hashTenantToken(tenantToken),
    });
    return { id: created.id, webhook_path: WEBHOOK_PREFIX + tenantToken };
  }

  async rotateToken(companyId: string): Promise<{ webhook_path: string }> {
    const existing = await this.repo.findActiveByCompany(companyId);
    if (!existing) {
      throw new NotFoundException('Integração Kommo não encontrada para esta empresa');
    }
    const tenantToken = this.crypto.generateTenantToken();
    await this.repo.update(existing.id, {
      tenant_token_hash: this.crypto.hashTenantToken(tenantToken),
    });
    return { webhook_path: WEBHOOK_PREFIX + tenantToken };
  }
}
