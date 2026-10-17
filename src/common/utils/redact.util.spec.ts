import { redactSecrets } from './redact.util';

describe('redactSecrets', () => {
  it('oculta o token do webhook', () => {
    expect(redactSecrets('/kommo/agendamento/abc123')).toBe('/kommo/agendamento/***');
  });

  it('mantém a query string', () => {
    expect(redactSecrets('/api/kommo/agendamento/abc123?x=1&y=2')).toBe(
      '/api/kommo/agendamento/***?x=1&y=2',
    );
  });

  it('não altera URLs sem token', () => {
    expect(redactSecrets('/customers?page=1')).toBe('/customers?page=1');
  });
});
