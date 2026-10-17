import { KommoEventRepository } from './kommo-event.repository';

function setup() {
  const calls: [string, any[]][] = [];
  const builder: any = new Proxy(() => {}, {
    get: (_t, prop: string) =>
      prop === 'then'
        ? (resolve: any) => resolve({ error: null })
        : (...args: any[]) => {
            calls.push([prop, args]);
            return builder;
          },
  });
  const repo = new KommoEventRepository({
    getClient: () => ({ from: (t: string) => (calls.push(['from', [t]]), builder) }),
  } as any);
  return { repo, calls };
}

describe('KommoEventRepository', () => {
  it.each([
    ['markDone', (r: KommoEventRepository) => r.markDone('e1', 'a1')],
    ['markFailed', (r: KommoEventRepository) => r.markFailed('e1', 'erro')],
    ['scheduleRetry', (r: KommoEventRepository) => r.scheduleRetry('e1', 'erro', new Date())],
  ])('%s só atualiza o evento em processing', async (_n, run) => {
    const { repo, calls } = setup();
    await run(repo);
    expect(calls).toContainEqual(['eq', ['id', 'e1']]);
    expect(calls).toContainEqual(['eq', ['status', 'processing']]);
  });
});
