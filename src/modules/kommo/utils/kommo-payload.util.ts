function toLeadId(value: unknown): number | null {
  const n = Number(value);
  return Number.isSafeInteger(n) && n > 0 ? n : null;
}

// O parser urlencoded pode gerar {"0": {...}} em vez de array.
function asArray(value: unknown): Record<string, any>[] {
  const items = Array.isArray(value)
    ? value
    : value && typeof value === 'object'
      ? Object.values(value)
      : [];
  return items.filter((item): item is Record<string, any> => !!item && typeof item === 'object');
}

export function extractLeadIds(body: unknown, scheduledStatusId: number): number[] {
  if (!body || typeof body !== 'object') return [];
  const b = body as Record<string, any>;
  const ids: number[] = [];

  const direct = toLeadId(b.lead_id ?? b.leadId);
  if (direct) ids.push(direct);

  const leads = b.leads && typeof b.leads === 'object' ? b.leads : {};
  for (const item of asArray(leads.status)) {
    if (Number(item.status_id) !== scheduledStatusId) continue;
    const id = toLeadId(item.id);
    if (id) ids.push(id);
  }
  for (const item of asArray(leads.add)) {
    if (item.status_id !== undefined && Number(item.status_id) !== scheduledStatusId) continue;
    const id = toLeadId(item.id);
    if (id) ids.push(id);
  }

  return [...new Set(ids)];
}
