export class KommoIntegration {
  id: string;
  company_id: string;
  company_unit_id: string;
  service_user_id: string;
  subdomain: string;
  access_token_encrypted: string;
  tenant_token_hash: string;
  pipeline_id: number;
  scheduled_status_id: number;
  date_field_id: number;
  time_field_id: number;
  referral_field_id: number | null;
  phone_field_id: number;
  timezone: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;

  constructor(partial: Partial<KommoIntegration>) {
    Object.assign(this, partial);
  }
}
