import { UserRole } from '@/common/enums';

export class User {
  id: string;
  full_name: string;
  email: string;
  password_hash: string;
  role: UserRole;
  created_at: string;
  updated_at: string;
  deleted_at: string | null;

  constructor(partial: Partial<User>) {
    Object.assign(this, partial);
  }
}

