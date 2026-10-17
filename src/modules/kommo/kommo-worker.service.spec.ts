import { KommoApiError } from './kommo-client';
import { KommoEvent } from './entities/kommo-event.entity';
import { KommoPermanentError } from './kommo-event-processor.service';
import { KommoWorkerService, backoffSeconds } from './kommo-worker.service';

describe('backoffSeconds', () => {
  it.each([
    [1, 30],
    [2, 60],
    [3, 120],
    [20, 3600],
  ])('tentativa %i → %is', (n, s) => expect(backoffSeconds(n)).toBe(s));
});

describe('KommoWorkerService', () => {
  let events: any;
  let processor: any;
  let config: any;
  let worker: KommoWorkerService;
  const ev = (id: string, attempts = 1) => new KommoEvent({ id, attempts });

  beforeEach(() => {
    events = {
      claim: vi.fn().mockResolvedValue([]),
      markDone: vi.fn(),
      markFailed: vi.fn(),
      scheduleRetry: vi.fn(),
    };
    processor = { process: vi.fn() };
    config = { get: vi.fn((k: string) => (k === 'app.kommoWorkerBatchSize' ? 10 : true)) };
    worker = new KommoWorkerService(events, processor, config);
  });

  afterEach(() => vi.useRealTimers());

  it('reivindica com lease e marca sucesso', async () => {
    events.claim.mockResolvedValue([ev('a')]);
    processor.process.mockResolvedValue('appt-1');
    await expect(worker.tick()).resolves.toBe(1);
    expect(events.claim).toHaveBeenCalledWith(3, 120);
    expect(events.markDone).toHaveBeenCalledWith('a', 'appt-1');
  });

  it('limita o claim ao tamanho do batch quando menor que o teto', async () => {
    config.get.mockImplementation((k: string) => (k === 'app.kommoWorkerBatchSize' ? 2 : true));
    await worker.tick();
    expect(events.claim).toHaveBeenCalledWith(2, 120);
  });

  it('erro permanente → failed sem retry', async () => {
    events.claim.mockResolvedValue([ev('a')]);
    processor.process.mockRejectedValue(new KommoPermanentError('Data inválida'));
    await worker.tick();
    expect(events.markFailed).toHaveBeenCalledWith('a', 'Data inválida');
    expect(events.scheduleRetry).not.toHaveBeenCalled();
  });

  it('401 do Kommo → failed sem retry', async () => {
    events.claim.mockResolvedValue([ev('a')]);
    processor.process.mockRejectedValue(new KommoApiError('Kommo respondeu 401', 401, false));
    await worker.tick();
    expect(events.markFailed).toHaveBeenCalledWith('a', 'Kommo respondeu 401');
  });

  it('erro transitório → retry com backoff', async () => {
    vi.useFakeTimers().setSystemTime(new Date('2026-10-14T12:00:00Z'));
    events.claim.mockResolvedValue([ev('a', 2)]);
    processor.process.mockRejectedValue(new KommoApiError('503', 503, true));
    await worker.tick();
    expect(events.scheduleRetry).toHaveBeenCalledWith('a', '503', new Date('2026-10-14T12:01:00Z'));
  });

  it('esgotou tentativas → failed', async () => {
    events.claim.mockResolvedValue([ev('a', 6)]);
    processor.process.mockRejectedValue(new Error('timeout'));
    await worker.tick();
    expect(events.markFailed).toHaveBeenCalledWith('a', 'timeout');
  });

  it('falha em um evento não impede os outros', async () => {
    events.claim.mockResolvedValue([ev('a'), ev('b')]);
    processor.process.mockRejectedValueOnce(new Error('x')).mockResolvedValueOnce('appt-b');
    await expect(worker.tick()).resolves.toBe(2);
    expect(events.markDone).toHaveBeenCalledWith('b', 'appt-b');
  });

  it('desligado por config não reivindica nada', async () => {
    config.get = vi.fn((k: string) => (k === 'app.kommoWorkerEnabled' ? false : 10));
    worker = new KommoWorkerService(events, processor, config);
    await expect(worker.tick()).resolves.toBe(0);
    expect(events.claim).not.toHaveBeenCalled();
  });

  it('tick reentrante na mesma instância é ignorado', async () => {
    let release!: () => void;
    events.claim.mockReturnValue(new Promise((r) => (release = () => r([]))));
    const first = worker.tick();
    await expect(worker.tick()).resolves.toBe(0);
    release();
    await first;
    expect(events.claim).toHaveBeenCalledTimes(1);
  });
});
