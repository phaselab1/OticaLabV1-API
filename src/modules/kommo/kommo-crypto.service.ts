import { Injectable } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { createCipheriv, createDecipheriv, createHash, randomBytes } from 'node:crypto';

const ALGO = 'aes-256-gcm';

@Injectable()
export class KommoCryptoService {
  private readonly key: Buffer;

  constructor(config: ConfigService) {
    this.key = Buffer.from(config.get<string>('app.kommoEncryptionKey') || '', 'base64');
    if (this.key.length !== 32) {
      throw new Error('KOMMO_ENCRYPTION_KEY deve ter 32 bytes em base64');
    }
  }

  generateTenantToken(): string {
    return randomBytes(32).toString('base64url');
  }

  hashTenantToken(token: string): string {
    return createHash('sha256').update(token).digest('hex');
  }

  encrypt(plain: string): string {
    const iv = randomBytes(12);
    const cipher = createCipheriv(ALGO, this.key, iv, { authTagLength: 16 });
    const data = Buffer.concat([cipher.update(plain, 'utf8'), cipher.final()]);
    return ['v1', iv, cipher.getAuthTag(), data].map((p) =>
      typeof p === 'string' ? p : p.toString('base64'),
    ).join(':');
  }

  decrypt(payload: string): string {
    const [, iv, tag, data] = payload.split(':');
    const decipher = createDecipheriv(ALGO, this.key, Buffer.from(iv, 'base64'), {
      authTagLength: 16,
    });
    decipher.setAuthTag(Buffer.from(tag, 'base64'));
    return Buffer.concat([
      decipher.update(Buffer.from(data, 'base64')),
      decipher.final(),
    ]).toString('utf8');
  }
}
