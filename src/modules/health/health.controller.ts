import { Controller, Get } from '@nestjs/common';
import { ApiOperation, ApiResponse, ApiTags } from '@nestjs/swagger';
import {
  HealthCheck,
  HealthCheckService,
  MemoryHealthIndicator,
} from '@nestjs/terminus';

@ApiTags('health')
@Controller('health')
export class HealthController {
  constructor(
    private readonly health: HealthCheckService,
    private readonly memory: MemoryHealthIndicator,
  ) {}

  @Get()
  @ApiOperation({ summary: 'Health check simples' })
  @ApiResponse({
    status: 200,
    description: 'API ativa e operante.',
  })
  simpleCheck() {
    return {
      status: 'ok',
      timestamp: new Date().toISOString(),
      uptime: process.uptime(),
    };
  }

  @Get('liveness')
  @ApiOperation({ summary: 'Kubernetes Liveness Probe' })
  liveness() {
    return { status: 'ok' };
  }

  @Get('readiness')
  @HealthCheck()
  @ApiOperation({ summary: 'Kubernetes Readiness Probe' })
  readiness() {
    return this.health.check([
      // Heap não pode ultrapassar 300MB
      () => this.memory.checkHeap('memory_heap', 300 * 1024 * 1024),
      // RSS não pode ultrapassar 500MB
      () => this.memory.checkRSS('memory_rss', 500 * 1024 * 1024),
    ]);
  }
}
