import { KommoApiError, KommoClient, fieldValue } from './kommo-client';

function res(status: number, body: unknown = {}) {
  return new Response(JSON.stringify(body), { status });
}

describe('KommoClient', () => {
  it('busca lead com contatos usando bearer e subdomínio', async () => {
    const fetchFn = vi.fn().mockResolvedValue(res(200, { id: 7, name: 'Lead' }));
    const client = new KommoClient('zyros', 'tok', fetchFn);
    await expect(client.getLead(7)).resolves.toMatchObject({ id: 7 });
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe('https://zyros.kommo.com/api/v4/leads/7?with=contacts');
    expect(init.headers.Authorization).toBe('Bearer tok');
  });

  it('cria nota comum no lead', async () => {
    const fetchFn = vi.fn().mockResolvedValue(res(200, {}));
    await new KommoClient('zyros', 'tok', fetchFn).addLeadNote(7, 'oi');
    const [url, init] = fetchFn.mock.calls[0];
    expect(url).toBe('https://zyros.kommo.com/api/v4/leads/7/notes');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body)).toEqual([{ note_type: 'common', params: { text: 'oi' } }]);
  });

  it.each([
    [401, false],
    [403, false],
    [404, false],
    [429, true],
    [500, true],
  ])('status %i → retryable %s', async (status, retryable) => {
    const fetchFn = vi.fn().mockResolvedValue(res(status));
    const err = await new KommoClient('z', 't', fetchFn).getLead(1).catch((e) => e);
    expect(err).toBeInstanceOf(KommoApiError);
    expect(err.status).toBe(status);
    expect(err.retryable).toBe(retryable);
  });

  it('erro de rede é retentável', async () => {
    const fetchFn = vi.fn().mockRejectedValue(new TypeError('fetch failed'));
    const err = await new KommoClient('z', 't', fetchFn).getLead(1).catch((e) => e);
    expect(err).toMatchObject({ retryable: true, status: 0 });
  });
});

describe('fieldValue', () => {
  const fields = [{ field_id: 614093, values: [{ value: '14:30' }] }];
  it('acha pelo id', () => expect(fieldValue(fields, 614093)).toBe('14:30'));
  it('ausente → null', () => expect(fieldValue(fields, 1)).toBeNull());
  it('lista nula → null', () => expect(fieldValue(null, 1)).toBeNull());
  it('fieldId nulo → null', () => expect(fieldValue(fields, null)).toBeNull());
});
