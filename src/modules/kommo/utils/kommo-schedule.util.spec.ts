import { parseSchedule } from './kommo-schedule.util';

const TZ = 'America/Araguaina';
// 2026-10-20 00:00 em Araguaína (UTC-3) = 2026-10-20T03:00:00Z
const LOCAL_MIDNIGHT = Date.UTC(2026, 9, 20, 3) / 1000;
// 2026-10-20 00:00Z = 2026-10-19 21:00 local
const UTC_MIDNIGHT = Date.UTC(2026, 9, 20, 0) / 1000;

describe('parseSchedule', () => {
  it('combina data local e HH:MM', () => {
    expect(parseSchedule(LOCAL_MIDNIGHT, '14:30', TZ)).toEqual({
      ok: true,
      scheduledAt: '2026-10-20T14:30:00-03:00',
      timeUnknown: false,
    });
  });

  it('aceita timestamp como string e H:MM', () => {
    expect(parseSchedule(String(LOCAL_MIDNIGHT), '8:05', TZ)).toEqual({
      ok: true,
      scheduledAt: '2026-10-20T08:05:00-03:00',
      timeUnknown: false,
    });
  });

  it('timestamp de meia-noite UTC continua sendo o mesmo dia civil', () => {
    expect(parseSchedule(UTC_MIDNIGHT, '09:00', TZ)).toMatchObject({
      scheduledAt: '2026-10-20T09:00:00-03:00',
    });
  });

  it.each([null, '', '25:00', '14h30', '14:7', 'manhã'])(
    'horário %s → 00:00 e timeUnknown',
    (time) => {
      expect(parseSchedule(LOCAL_MIDNIGHT, time, TZ)).toEqual({
        ok: true,
        scheduledAt: '2026-10-20T00:00:00-03:00',
        timeUnknown: true,
      });
    },
  );

  it.each([null, '', 'amanhã', 0, -5])('data %s → erro', (date) => {
    expect(parseSchedule(date, '10:00', TZ)).toEqual({
      ok: false,
      reason: 'Data do agendamento vazia ou inválida',
    });
  });
});

describe('parseSchedule (timestamp fora do intervalo)', () => {
  it.each([1e13, 1760000000000])('timestamp %s → erro', (date) => {
    expect(parseSchedule(date, '10:00', TZ)).toEqual({
      ok: false,
      reason: 'Data do agendamento vazia ou inválida',
    });
  });
});
