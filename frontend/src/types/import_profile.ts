export type ReconciliationType = "sales" | "purchases";
export type ProfileScope = "builtin" | "company";
export type SourceFormat = "csv" | "xlsx";

export interface ParsingHints {
  has_header: boolean;
  header_row: number;
  data_start_row: number;
  sheet_name?: string | null;
  delimiter: string;
  date_format: string;
  decimal_separator: string;
  thousands_separator: string;
}

export interface CanonicalColumnMapping {
  pin: string[];
  partner_name: string[];
  invoice_number: string[];
  invoice_date: string[];
  cu_number: string[];
  vat_group: string[];
  base_amount: string[];
}

export interface SalesValidationRules {
  module: "sales";
  required_fields: string[];
  allowed_vat_codes: string[];
  date_strictness: "STRICT" | "LENIENT";
  row_skip_policy: "SKIP_EMPTY_AND_TOTALS" | "FAIL_ON_EMPTY";
  default_vat_group: string;
  require_valid_pin_format: boolean;
}

export interface PurchasesValidationRules {
  module: "purchases";
  required_fields: string[];
  allowed_vat_codes: string[];
  date_strictness: "STRICT" | "LENIENT";
  row_skip_policy: "SKIP_EMPTY_AND_TOTALS" | "FAIL_ON_EMPTY";
  default_vat_group: string;
  purchase_cu_fallback_field?: string | null;
}

export type TypedValidationRules = SalesValidationRules | PurchasesValidationRules;

export interface ImportProfile {
  id: number;
  company_id?: number | null;
  scope: ProfileScope;
  name: string;
  module: ReconciliationType;
  provider: string;
  description?: string | null;
  source_format: SourceFormat;
  parsing_hints: ParsingHints;
  column_mapping: CanonicalColumnMapping;
  validation_rules: TypedValidationRules;
  is_builtin: boolean;
  is_default: boolean;
  is_active: boolean;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface ImportProfileCreate {
  name: string;
  module: ReconciliationType;
  provider: string;
  description?: string;
  source_format: SourceFormat;
  parsing_hints: ParsingHints;
  column_mapping: CanonicalColumnMapping;
  validation_rules: TypedValidationRules;
  is_default: boolean;
}

export interface PreviewRowSample {
  row_index: number;
  raw_values: Record<string, string>;
  mapped_invoice: {
    pin: string;
    partner_name: string;
    invoice_number: string;
    invoice_date?: string | null;
    cu_number: string;
    vat_group: string;
    base_amount?: number | null;
  };
  validation_errors: string[];
}

export interface MappingPreviewResponse {
  filename: string;
  detected_headers: string[];
  total_rows_detected: number;
  preview_samples: PreviewRowSample[];
  is_valid: boolean;
  general_errors: List[string];
}
