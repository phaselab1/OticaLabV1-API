import { MiddlewareConsumer, Module, NestModule } from '@nestjs/common';
import { ConfigModule } from '@nestjs/config';
import { ThrottlerModule, ThrottlerGuard } from '@nestjs/throttler';
import { APP_GUARD } from '@nestjs/core';
import appConfig from './config/app.config';
import { DatabaseModule } from './core/database/database.module';
import { SecurityModule } from './core/security/security.module';
import { HttpLoggerMiddleware } from './common/middlewares/http-logger.middleware';
import { AppointmentsModule } from './modules/appointments/appointments.module';
import { AuthModule } from './modules/auth/auth.module';
import { CompaniesModule } from './modules/companies/companies.module';
import { CustomersModule } from './modules/customers/customers.module';
import { HealthModule } from './modules/health/health.module';
import { UsersModule } from './modules/users/users.module';

@Module({
  imports: [
    ConfigModule.forRoot({
      isGlobal: true,
      load: [appConfig],
      envFilePath: ['.env', '.env.local'],
    }),
    // Rate Limiting global (100 requisições por minuto por IP)
    ThrottlerModule.forRoot([
      {
        ttl: 60000,
        limit: 100,
      },
    ]),
    DatabaseModule,
    SecurityModule,
    HealthModule,
    AuthModule,
    UsersModule,
    CompaniesModule,
    CustomersModule,
    AppointmentsModule,
  ],
  providers: [
    {
      provide: APP_GUARD,
      useClass: ThrottlerGuard,
    },
  ],
})
export class AppModule implements NestModule {
  configure(consumer: MiddlewareConsumer) {
    consumer.apply(HttpLoggerMiddleware).forRoutes('*');
  }
}
