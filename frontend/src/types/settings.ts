export type BaseAmountPolicy = "allow" | "skip" | "reject" | "reject_session" | "treat_as_zero";
export type UnmappedVatPolicy = "reject_invoice" | "needs_review";
export type VatModule = "sales" | "purchases";

// SAP field holding the Purchase Invoice CU number. Values are the exact SAP field names.
export type PurchaseCUField = "U_CUINV" | "NumAtCard" | "Comments" | "JournalMemo" | "Reference1";

export interface SAPConnection {
  id: number;
  name: string;
  base_url: string;
  company_db: string;
  username: string;
  password_set: boolean;
  verify_ssl: boolean;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface SystemSettings {
  id: number;
  active_connection_id: number | null;
  amount_tolerance: string;
  base_amount_policy: BaseAmountPolicy;
  unmapped_vat_policy: UnmappedVatPolicy;
  ignore_missing_cu: boolean;
  include_credit_notes: boolean;
  include_debit_notes: boolean;
  skip_cancelled: boolean;
  sales_cu_source: string;
  purchase_cu_source: string;
  kra_parsing_profiles?: KRAParsingProfilesConfig | null;
  version: number;
  updated_at: string;
  warning?: string | null;
}

export interface KRAParsingProfileItem {
  pin_column: number;
  partner_name_column: number;
  invoice_number_column: number | null;
  invoice_date_column: number;
  cu_number_column: number;
  base_amount_column: number;
}

export interface KRAParsingProfilesConfig {
  schema_version: number;
  profiles: Record<string, KRAParsingProfileItem>;
}

export interface VATMappingItem {
  id?: number;
  module: VatModule;
  sap_code: string;
  description: string;
  canonical_rate: string;
  is_builtin: boolean;
  created_at?: string;
}

export interface KRAVATMappingItem {
  id?: number;
  section_prefix: string;
  canonical_rate: string;
  description?: string;
}

export interface SettingsComposite {
  sap_connection: SAPConnection | null;
  system_settings: SystemSettings;
  vat_mappings: VATMappingItem[];
  kra_vat_mappings: KRAVATMappingItem[];
  is_using_env_fallback: boolean;
}

export interface StepResult {
  status: "pass" | "fail" | "warn";
  message: string;
}

export interface TestConnectionResponse {
  connected: boolean;
  steps: Record<string, StepResult>;
  error_message?: string | null;
  metadata?: {
    system_version?: string;
    company_name?: string;
    connected_user?: string;
    database_name?: string;
    latency_ms?: number;
  } | null;
}

export interface SettingAuditLog {
  id: number;
  user_id: number | null;
  user_email: string | null;
  action: string;
  changes_json: Record<string, { old: unknown; new: unknown }>;
  reason?: string | null;
  created_at: string;
}
