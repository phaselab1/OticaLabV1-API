import { classifyCustomerMatch } from './customer-matching';

describe('classifyCustomerMatch', () => {
  it('sem candidatos → novo', () => {
    expect(classifyCustomerMatch([])).toEqual({ kind: 'new' });
  });

  it.each([0.85, 0.97, 1])('score %s → reutiliza', (score) => {
    expect(classifyCustomerMatch([{ id: 'a', score }])).toEqual({ kind: 'reuse', id: 'a' });
  });

  it.each([0.6, 0.7, 0.849])('score %s → possível duplicado', (score) => {
    expect(classifyCustomerMatch([{ id: 'a', score }])).toEqual({
      kind: 'possible_duplicate',
      id: 'a',
    });
  });

  it.each([0, 0.3, 0.599])('score %s → novo (outro membro da família)', (score) => {
    expect(classifyCustomerMatch([{ id: 'a', score }])).toEqual({ kind: 'new' });
  });

  it('usa o melhor candidato mesmo fora de ordem', () => {
    expect(
      classifyCustomerMatch([
        { id: 'pai', score: 0.2 },
        { id: 'filha', score: 0.9 },
      ]),
    ).toEqual({ kind: 'reuse', id: 'filha' });
  });
});
