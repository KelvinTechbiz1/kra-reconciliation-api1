import { fetchWithAuth } from "@/lib/api";
import { Invoice, ReconciliationResult, ReconciliationSummary } from "../types";
import {
  PaginatedResponse,
  PaginatedResultsResponse,
  ResultFilter,
  ResultSortField,
  ResultSortOrder,
} from "@/types";

export interface InvoiceFetchResponse {
  session_id: string;
  source: string;
  /** Rows this call added — one window's worth, not the whole range. */
  count: number;
  /** Running total of SAP rows in the session across every window loaded so far. */
  total_sap_records?: number;
  from_date: string;
  to_date: string;
  invoices: Invoice[];
  profile_name?: string | null;
  provider?: string | null;
}


export interface CSVValidationErrorDetail {
  row: number;
  column: string | null;
  message: string;
}

export interface FileUploadStatus {
  filename: string;
  rows: number;
  parsed: number;
  errors_count: number;
  errors: CSVValidationErrorDetail[];
}

/**
 * A file tag in the workspace: either a status the server returned, or a placeholder
 * standing in for one whose upload is still in flight.
 */
export type KraFileTag = FileUploadStatus & { pending?: boolean };

export interface MultipleInvoiceUploadResponse {
  session_id: string;
  files: FileUploadStatus[];
  invoices: Invoice[];
  /** Rows this request added. KRA uploads append to the session. */
  added: number;
  /** Rows already present in the session and therefore not re-imported. */
  duplicates_skipped: number;
  /** Running total of KRA rows in the session across all uploads. */
  total_kra_records: number;
}

export interface ReconciliationResponse {
  session_id: string;
  summary: ReconciliationSummary;
}

/**
 * Fetch one window of SAP data. Passing `sessionId` appends to that session instead of
 * starting a new one, which is how a long date range is loaded a piece at a time.
 */
export async function fetchInvoicesPreview(
  type: "sales" | "purchases",
  fromDate: string,
  toDate: string,
  sessionId?: string
): Promise<InvoiceFetchResponse> {
  const params = new URLSearchParams({ from: fromDate, to: toDate });
  if (sessionId) params.set("session_id", sessionId);

  const res = await fetchWithAuth(`/${type}?${params}`);
  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Failed to load SAP data");
  }
  return res.json();
}

/**
 * Split a date range into contiguous windows so the table can fill as each one returns.
 *
 * Short ranges stay a single request: splitting them would add round trips without
 * shortening the wait enough to notice. Both bounds are inclusive and windows never
 * overlap, so no invoice is fetched twice.
 */
export function splitDateRange(
  fromDate: string,
  toDate: string,
  windowDays = 7,
  minDaysToSplit = 10
): Array<{ from: string; to: string }> {
  const start = new Date(`${fromDate}T00:00:00Z`);
  const end = new Date(`${toDate}T00:00:00Z`);

  if (isNaN(start.getTime()) || isNaN(end.getTime()) || end < start) {
    return [{ from: fromDate, to: toDate }];
  }

  const dayMs = 86_400_000;
  const spanDays = Math.round((end.getTime() - start.getTime()) / dayMs) + 1;
  if (spanDays <= minDaysToSplit) return [{ from: fromDate, to: toDate }];

  const iso = (d: Date) => d.toISOString().slice(0, 10);
  const windows: Array<{ from: string; to: string }> = [];

  for (let t = start.getTime(); t <= end.getTime(); t += windowDays * dayMs) {
    const windowEnd = new Date(Math.min(t + (windowDays - 1) * dayMs, end.getTime()));
    windows.push({ from: iso(new Date(t)), to: iso(windowEnd) });
  }
  return windows;
}

export async function uploadInvoicesCSV(
  type: "sales" | "purchases",
  sessionId: string,
  files: File[]
): Promise<MultipleInvoiceUploadResponse> {
  const formData = new FormData();
  files.forEach(file => formData.append("files", file));

  const res = await fetchWithAuth(`/${type}/upload?session_id=${sessionId}`, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Failed to upload KRA CSV");
  }
  return res.json();
}

export interface KRAFileRemovalResponse {
  session_id: string;
  filename: string;
  /** Rows deleted. Zero is legitimate — a file that failed to parse contributed none. */
  removed: number;
  total_kra_records: number;
  /** Files the session still holds, per the server. */
  remaining_files: string[];
}

/** Drop one uploaded KRA CSV from the session without abandoning the whole session. */
export async function removeKraFile(
  type: "sales" | "purchases",
  sessionId: string,
  filename: string
): Promise<KRAFileRemovalResponse> {
  const params = new URLSearchParams({ session_id: sessionId, filename });
  const res = await fetchWithAuth(`/${type}/upload?${params}`, { method: "DELETE" });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    throw new Error(data.detail || "Failed to remove KRA CSV");
  }
  return res.json();
}

export async function compareInvoices(sessionId: string): Promise<ReconciliationResponse> {
  const res = await fetchWithAuth(`/reconciliation/compare`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId }),
  });

  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Reconciliation failed");
  }
  return res.json();
}

export async function fetchInvoicesPage(
  sessionId: string,
  source: "SAP" | "KRA",
  page: number,
  limit: number
): Promise<PaginatedResponse<Invoice>> {
  const res = await fetchWithAuth(`/sessions/${sessionId}/invoices?source=${source}&page=${page}&limit=${limit}`);
  if (!res.ok) {
    throw new Error("Failed to fetch invoices");
  }
  return res.json();
}

export async function fetchReconciliationResultsPage(
  sessionId: string,
  page: number,
  limit: number,
  statusFilter: ResultFilter = "All",
  sortField: ResultSortField | null = null,
  sortOrder: ResultSortOrder = "asc"
): Promise<PaginatedResultsResponse<ReconciliationResult>> {
  const params = new URLSearchParams({
    page: String(page),
    limit: String(limit),
    status_filter: statusFilter,
  });
  if (sortField) {
    params.set("sort_field", sortField);
    params.set("sort_order", sortOrder);
  }
  const res = await fetchWithAuth(`/sessions/${sessionId}/results?${params}`);
  if (!res.ok) {
    throw new Error("Failed to fetch reconciliation results");
  }
  return res.json();
}

export async function uploadErpInvoices(
  type: "sales" | "purchases",
  files: File[],
  profileId?: number | null,
  sessionId?: string | null
): Promise<InvoiceFetchResponse> {
  const formData = new FormData();
  files.forEach(file => formData.append("files", file));

  let url = `/${type}/upload-erp`;
  const params: string[] = [];
  if (profileId) params.push(`profile_id=${profileId}`);
  if (sessionId) params.push(`session_id=${sessionId}`);
  if (params.length > 0) url += `?${params.join("&")}`;

  const res = await fetchWithAuth(url, {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Failed to upload ERP file");
  }
  return res.json();
}

