export type UserRole = "admin" | "company_admin" | "checker";

export interface UserRecord {
  id: number;
  username: string;
  email: string | null;
  full_name: string | null;
  role: UserRole;
  company_id?: number | null;
  /** Name of the user's company. Null for SaaS admins, who belong to none. */
  company_name?: string | null;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserCreatePayload {
  username: string;
  password?: string;
  email?: string;
  full_name?: string;
  role: UserRole;
  company_id?: number | null;
}

export interface UserUpdatePayload {
  username?: string;
  email?: string;
  full_name?: string;
  role?: UserRole;
  company_id?: number | null;
  is_active?: boolean;
}

export interface UserPasswordResetPayload {
  new_password: string;
}

export interface CompanyProfile {
  id: number;
  name: string;
  kra_pin: string | null;
  timezone: string;
  currency: string;
  fiscal_year_start_month: number;
  created_at: string;
  updated_at: string;
}

export interface CompanyCreatePayload {
  name: string;
  kra_pin?: string;
  timezone?: string;
  currency?: string;
  fiscal_year_start_month?: number;
}

export interface CompanyUpdatePayload {
  name?: string;
  kra_pin?: string;
  timezone?: string;
  currency?: string;
  fiscal_year_start_month?: number;
}
