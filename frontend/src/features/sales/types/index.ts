export interface Invoice {
  pin: string;
  partner_name: string;
  invoice_number: string;
  invoice_date: string;
  cu_number: string;
  vat_group: string;
  base_amount: number;
  source: string;
}

export interface ReconciliationResult {
  cu_number: string;
  status: string;
  invoice_type?: string;
  amount_match: boolean;
  vat_match: boolean;
  date_match: boolean;
  partner_name_matches: boolean;
  pin_matches: boolean;
  sap: Invoice | null;
  kra: Invoice | null;

  sap_base_16?: number;
  sap_base_8?: number;
  sap_base_0?: number;
  sap_base_exempt?: number;

  kra_base_16?: number;
  kra_base_8?: number;
  kra_base_0?: number;
  kra_base_exempt?: number;
}

export interface ReconciliationSummary {
  total_sap: number;
  total_kra: number;
  matches: number;
  mismatches: number;
  missing_in_sap: number;
  missing_in_kra: number;
  missing_cu?: number;
}
