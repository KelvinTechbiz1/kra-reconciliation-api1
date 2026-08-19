/** Filter chips on the reconciliation results table. Must match RESULT_FILTERS
 * in app/domain/reconciliation_constants.py — the server does the filtering. */
export const RESULT_FILTERS = [
  "All",
  "Issues",
  "Matches",
  "Missing CU",
  "Missing SAP",
  "Missing KRA",
  "Amount",
  "VAT",
  "CU",
  "PIN",
  "Multiple",
] as const;

export type ResultFilter = (typeof RESULT_FILTERS)[number];

export interface PaginatedResponse<T> {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  items: T[];
}

export interface PaginatedResultsResponse<T> extends PaginatedResponse<T> {
  status_filter: ResultFilter;
  /** Whole-session totals per chip, so the chips are complete on the first page. */
  status_counts: Partial<Record<ResultFilter, number>>;
}
