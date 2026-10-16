import { INestApplication, ValidationPipe } from '@nestjs/common';
import { NestExpressApplication } from '@nestjs/platform-express';
import { Test } from '@nestjs/testing';
import request from 'supertest';
import { KommoWebhookController } from './kommo-webhook.controller';
import { KommoWebhookService } from './kommo-webhook.service';
import { extractLeadIds } from './utils/kommo-payload.util';

const TOKEN = 'a'.repeat(43);
const STATUS_ID = 112039795;

describe('KommoWebhookController', () => {
  let app: INestApplication;
  const service = { ingest: vi.fn() };

  beforeAll(async () => {
    const moduleRef = await Test.createTestingModule({
      controllers: [KommoWebhookController],
      providers: [{ provide: KommoWebhookService, useValue: service }],
    }).compile();
    const nest = moduleRef.createNestApplication<NestExpressApplication>();
    nest.useBodyParser('urlencoded', { extended: true, limit: '1mb' });
    nest.useGlobalPipes(
      new ValidationPipe({
        whitelist: true,
        transform: true,
        forbidNonWhitelisted: true,
        transformOptions: { enableImplicitConversion: true },
      }),
    );
    await nest.init();
    app = nest;
  });

  afterAll(() => app.close());

  beforeEach(() => {
    service.ingest.mockReset().mockResolvedValue({ queued: 1 });
  });

  it('form-urlencoded aninhado chega ao service como objeto', async () => {
    await request(app.getHttpServer())
      .post(`/kommo/agendamento/${TOKEN}`)
      .type('form')
      .send('leads[status][0][id]=123&leads[status][0][status_id]=112039795')
      .expect(200, { ok: true, queued: 1 });

    const [token, body] = service.ingest.mock.calls[0];
    expect(token).toBe(TOKEN);
    expect(extractLeadIds(body, STATUS_ID)).toEqual([123]);
  });

  it('JSON chega inalterado ao service', async () => {
    await request(app.getHttpServer())
      .post(`/kommo/agendamento/${TOKEN}`)
      .send({ lead_id: 123 })
      .expect(200, { ok: true, queued: 1 });

    expect(service.ingest).toHaveBeenCalledWith(TOKEN, { lead_id: 123 });
  });
});
