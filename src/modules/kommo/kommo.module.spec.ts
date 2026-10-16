import { ConfigModule } from '@nestjs/config';
import { Test } from '@nestjs/testing';
import { DatabaseModule } from '@/core/database/database.module';
import { SecurityModule } from '@/core/security/security.module';
import { SupabaseService } from '@/core/database/supabase.service';
import { KommoEventProcessorService } from './kommo-event-processor.service';
import { KommoWorkerService } from './kommo-worker.service';
import { KommoModule } from './kommo.module';

describe('KommoModule', () => {
  it('resolve o KommoEventProcessorService e o KommoWorkerService via DI', async () => {
    const moduleRef = await Test.createTestingModule({
      imports: [
        ConfigModule.forRoot({
          isGlobal: true,
          ignoreEnvFile: true,
          load: [
            () => ({ app: { kommoEncryptionKey: Buffer.alloc(32, 1).toString('base64') } }),
          ],
        }),
        DatabaseModule,
        SecurityModule,
        KommoModule,
      ],
    })
      .overrideProvider(SupabaseService)
      .useValue({ getClient: () => ({}) })
      .compile();

    expect(moduleRef.get(KommoEventProcessorService)).toBeInstanceOf(KommoEventProcessorService);
    expect(moduleRef.get(KommoWorkerService)).toBeInstanceOf(KommoWorkerService);
  });
});
