import { normalizePhone, phoneVariants } from './phone.util';

describe('normalizePhone', () => {
  it.each([
    ['+55 (63) 99123-4567', '63991234567'],
    ['5563991234567', '63991234567'],
    ['63 3215-1234', '6332151234'],
    ['(63) 9123-4567', '6391234567'],
    ['055 63 99123 4567', '63991234567'],
  ])('%s → %s', (raw, expected) => {
    expect(normalizePhone(raw)).toBe(expected);
  });

  it.each([null, undefined, '', 'abc', '12345', '+1 415 555 0100 99'])(
    'retorna null para %s',
    (raw) => {
      expect(normalizePhone(raw as any)).toBeNull();
    },
  );

  it('12 dígitos começando com 55 perde o código do país', () => {
    expect(normalizePhone('556391234567')).toBe('6391234567');
  });

  it('11 dígitos começando com 55 é DDD 55, não código do país', () => {
    expect(normalizePhone('55991234567')).toBe('55991234567');
  });
});

describe('phoneVariants', () => {
  it('celular com 9 também gera sem 9', () => {
    expect(phoneVariants('63991234567')).toEqual(['63991234567', '6391234567']);
  });

  it('celular sem 9 também gera com 9', () => {
    expect(phoneVariants('6391234567')).toEqual(['6391234567', '63991234567']);
  });

  it('fixo não ganha variante', () => {
    expect(phoneVariants('6332151234')).toEqual(['6332151234']);
  });
});
