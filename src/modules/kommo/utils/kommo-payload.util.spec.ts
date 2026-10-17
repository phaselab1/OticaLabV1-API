import { extractLeadIds } from './kommo-payload.util';

const STAGE = 112039795;

describe('extractLeadIds', () => {
  it('webhook nativo leads[status] filtra pela etapa', () => {
    const body = {
      leads: {
        status: [
          { id: '111', status_id: String(STAGE), pipeline_id: '14505231' },
          { id: '222', status_id: '999' },
        ],
      },
    };
    expect(extractLeadIds(body, STAGE)).toEqual([111]);
  });

  it('aceita objeto indexado ({"0": {...}}) vindo do urlencoded', () => {
    const body = { leads: { status: { '0': { id: '111', status_id: String(STAGE) } } } };
    expect(extractLeadIds(body, STAGE)).toEqual([111]);
  });

  it('leads[add] sem status_id é aceito', () => {
    expect(extractLeadIds({ leads: { add: [{ id: '333' }] } }, STAGE)).toEqual([333]);
  });

  it('corpo customizado com lead_id', () => {
    expect(extractLeadIds({ lead_id: '444' }, STAGE)).toEqual([444]);
  });

  it('remove duplicados', () => {
    const body = { lead_id: '5', leads: { status: [{ id: '5', status_id: String(STAGE) }] } };
    expect(extractLeadIds(body, STAGE)).toEqual([5]);
  });

  it.each([null, {}, { lead_id: 'abc' }, { leads: 'x' }])('payload %j → []', (body) => {
    expect(extractLeadIds(body, STAGE)).toEqual([]);
  });
});

describe('extractLeadIds (itens inválidos)', () => {
  it.each([
    { leads: { status: [null] } },
    { leads: { add: ['x'] } },
  ])('payload %j → []', (body) => {
    expect(extractLeadIds(body, STAGE)).toEqual([]);
  });

  it('item válido misturado com inválido retorna só o válido', () => {
    const body = { leads: { status: [null, 'x', { id: '777', status_id: String(STAGE) }] } };
    expect(extractLeadIds(body, STAGE)).toEqual([777]);
  });
});
