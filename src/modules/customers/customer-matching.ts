export type CustomerCandidate = { id: string; score: number };

export type CustomerMatch =
  | { kind: 'reuse'; id: string }
  | { kind: 'possible_duplicate'; id: string }
  | { kind: 'new' };

export const SAME_PERSON_THRESHOLD = 0.85;
export const POSSIBLE_DUPLICATE_THRESHOLD = 0.6;

export function classifyCustomerMatch(candidates: CustomerCandidate[]): CustomerMatch {
  const best = candidates.reduce<CustomerCandidate | null>(
    (acc, c) => (!acc || c.score > acc.score ? c : acc),
    null,
  );
  if (!best) return { kind: 'new' };
  if (best.score >= SAME_PERSON_THRESHOLD) return { kind: 'reuse', id: best.id };
  if (best.score >= POSSIBLE_DUPLICATE_THRESHOLD) return { kind: 'possible_duplicate', id: best.id };
  return { kind: 'new' };
}
