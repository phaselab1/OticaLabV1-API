export class KommoApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly retryable: boolean,
  ) {
    super(message);
  }
}

export interface KommoCustomField {
  field_id: number;
  values: { value: unknown }[];
}

export interface KommoLead {
  id: number;
  name: string;
  status_id: number;
  pipeline_id: number;
  custom_fields_values: KommoCustomField[] | null;
  _embedded?: { contacts?: { id: number; is_main: boolean }[] };
}

export interface KommoContact {
  id: number;
  name: string;
  custom_fields_values: KommoCustomField[] | null;
}

export function fieldValue(
  fields: KommoCustomField[] | null | undefined,
  fieldId: number | null,
): unknown {
  if (!fields || fieldId === null) return null;
  const field = fields.find((f) => Number(f.field_id) === Number(fieldId));
  return field?.values?.[0]?.value ?? null;
}

const TIMEOUT_MS = 10_000;

export class KommoClient {
  private readonly baseUrl: string;

  constructor(
    subdomain: string,
    private readonly accessToken: string,
    private readonly fetchFn: typeof fetch = fetch,
  ) {
    this.baseUrl = `https://${subdomain}.kommo.com/api/v4`;
  }

  getLead(id: number): Promise<KommoLead> {
    return this.request(`/leads/${id}?with=contacts`);
  }

  getContact(id: number): Promise<KommoContact> {
    return this.request(`/contacts/${id}`);
  }

  async addLeadNote(leadId: number, text: string): Promise<void> {
    await this.request(`/leads/${leadId}/notes`, {
      method: 'POST',
      body: JSON.stringify([{ note_type: 'common', params: { text } }]),
    });
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    let response: Response;
    try {
      response = await this.fetchFn(`${this.baseUrl}${path}`, {
        ...init,
        headers: {
          Authorization: `Bearer ${this.accessToken}`,
          'Content-Type': 'application/json',
        },
        signal: AbortSignal.timeout(TIMEOUT_MS),
      });
    } catch (err) {
      throw new KommoApiError(`Falha de rede no Kommo: ${(err as Error).message}`, 0, true);
    }

    if (!response.ok) {
      const retryable = response.status === 429 || response.status >= 500;
      throw new KommoApiError(`Kommo respondeu ${response.status} em ${path}`, response.status, retryable);
    }
    return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
  }
}
