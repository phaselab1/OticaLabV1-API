export class Customer {
  id: string;
  company_id: string;
  company_unit_id: string;
  full_name: string;
  phone: string;
  created_by_user_id: string;
  updated_by_user_id: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;

  constructor(partial: Partial<Customer>) {
    Object.assign(this, partial);
  }
}

