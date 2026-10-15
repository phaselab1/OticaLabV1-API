export class Customer {
  id: string;
  company_id: string;
  company_unit_id: string;
  full_name: string;
  phone: string | null;
  kommo_contact_id: number | null;
  needs_review: boolean;
  review_reason: string | null;
  created_by_user_id: string;
  updated_by_user_id: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;

  constructor(partial: Partial<Customer>) {
    Object.assign(this, partial);
  }
}

