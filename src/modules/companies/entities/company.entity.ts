export class Company {
  id: string;
  name: string;
  cnpj: string;
  state: string;
  city: string;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;

  constructor(partial: Partial<Company>) {
    Object.assign(this, partial);
  }
}

export class CompanyUnit {
  id: string;
  company_id: string;
  name: string;
  code: string;
  cnpj: string;
  state: string;
  city: string;
  created_by_user_id: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;

  constructor(partial: Partial<CompanyUnit>) {
    Object.assign(this, partial);
  }
}

export class CompanyUserLink {
  id: string;
  company_id: string;
  user_id: string;
  unit_id: string | null;
  granted_by_user_id: string;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;

  constructor(partial: Partial<CompanyUserLink>) {
    Object.assign(this, partial);
  }
}

