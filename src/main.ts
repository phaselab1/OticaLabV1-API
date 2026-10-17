import { ValidationPipe } from '@nestjs/common';
import { ConfigService } from '@nestjs/config';
import { NestFactory } from '@nestjs/core';
import { DocumentBuilder, SwaggerModule } from '@nestjs/swagger';
import compression from 'compression';
import helmet from 'helmet';
import { AppModule } from './app.module';
import { AllExceptionsFilter } from './common/filters/all-exceptions.filter';
import { ResponseTransformInterceptor } from './common/interceptors/response-transform.interceptor';

async function bootstrap() {
  const app = await NestFactory.create(AppModule);
  const configService = app.get(ConfigService);

  // 1. Hardening de cabeçalhos HTTP para produção (Helmet)
  app.use(helmet());

  // 2. Compressão Gzip/Brotli de payloads de resposta (Economia de rede e latência)
  app.use(compression());

  // 3. Filtro global de exceções padronizado
  app.useGlobalFilters(new AllExceptionsFilter());

  // 4. Interceptor global para normalização
  app.useGlobalInterceptors(new ResponseTransformInterceptor());

  // 5. Validação global estrita com parsing e sanitização de payloads
  app.useGlobalPipes(
    new ValidationPipe({
      whitelist: true,
      transform: true,
      forbidNonWhitelisted: true,
      transformOptions: { enableImplicitConversion: true },
    }),
  );

  // 6. Shutdown gracioso para escala horizontal (K8s / ECS SIGTERM / SIGINT)
  app.enableShutdownHooks();

  // 7. CORS
  const corsOrigins = configService.get<string[]>('app.corsAllowedOrigins');
  if (corsOrigins && corsOrigins.length > 0) {
    app.enableCors({
      origin: corsOrigins,
      credentials: true,
    });
  }

  // 8. Swagger OpenAPI
  const config = new DocumentBuilder()
    .setTitle('Otica Lab API')
    .setDescription(
      'API Corporativa do Ótica Lab — Multi-Tenant, Alta Disponibilidade e Escalabilidade Horizontal.',
    )
    .setVersion('1.0.0')
    .addBearerAuth()
    .build();

  const document = SwaggerModule.createDocument(app, config);
  SwaggerModule.setup('docs', app, document);

  const port = configService.get<number>('app.port') || 8000;
  await app.listen(port, '0.0.0.0');
  console.log(`[READY] Server running on http://localhost:${port}`);
  console.log(`[DOCS] Swagger UI available at http://localhost:${port}/docs`);
}

bootstrap();
