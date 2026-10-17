export type ScheduleResult =
  | { ok: true; scheduledAt: string; timeUnknown: boolean }
  | { ok: false; reason: string };

const TIME_RE = /^([01]?\d|2[0-3]):([0-5]\d)$/;

function offsetFor(date: Date, timezone: string): string {
  const name = new Intl.DateTimeFormat('en-US', {
    timeZone: timezone,
    timeZoneName: 'longOffset',
  })
    .formatToParts(date)
    .find((p) => p.type === 'timeZoneName')!.value;
  const offset = name.replace('GMT', '');
  return offset === '' ? '+00:00' : offset;
}

function localDay(date: Date, timezone: string): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: timezone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}

export function parseSchedule(
  dateUnix: unknown,
  time: unknown,
  timezone: string,
): ScheduleResult {
  const seconds = Number(dateUnix);
  if (dateUnix === null || dateUnix === '' || !Number.isFinite(seconds) || seconds <= 0) {
    return { ok: false, reason: 'Data do agendamento vazia ou inválida' };
  }

  const instant = new Date(seconds * 1000);
  const year = instant.getUTCFullYear();
  if (Number.isNaN(instant.getTime()) || year < 2000 || year > 2100) {
    return { ok: false, reason: 'Data do agendamento vazia ou inválida' };
  }
  // Campo data às vezes vem como 00:00Z, que cai no dia anterior em UTC-3.
  const isUtcMidnight = instant.getUTCHours() === 0 && instant.getUTCMinutes() === 0;
  const day = isUtcMidnight
    ? instant.toISOString().slice(0, 10)
    : localDay(instant, timezone);

  const match = typeof time === 'string' ? TIME_RE.exec(time.trim()) : null;
  const hhmm = match ? `${match[1].padStart(2, '0')}:${match[2]}` : '00:00';

  return {
    ok: true,
    scheduledAt: `${day}T${hhmm}:00${offsetFor(new Date(`${day}T12:00:00Z`), timezone)}`,
    timeUnknown: !match,
  };
}
