import { fetchWithAuth } from "@/lib/api";
import { Invoice, ReconciliationResult, ReconciliationSummary } from "../types";
import { PaginatedResponse } from "@/types";

export interface InvoiceFetchResponse {
  session_id: string;
  source: string;
  count: number;
  from_date: string;
  to_date: string;
  invoices: Invoice[];
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

export interface MultipleInvoiceUploadResponse {
  session_id: string;
  files: FileUploadStatus[];
  invoices: Invoice[];
}

export interface ReconciliationResponse {
  session_id: string;
  summary: ReconciliationSummary;
}

export async function fetchInvoicesPreview(
  type: "sales" | "purchases",
  fromDate: string,
  toDate: string
): Promise<InvoiceFetchResponse> {
  const res = await fetchWithAuth(`/${type}?from=${fromDate}&to=${toDate}`);
  if (!res.ok) {
    const data = await res.json();
    throw new Error(data.detail || "Failed to load SAP data");
  }
  return res.json();
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
  limit: number
): Promise<PaginatedResponse<ReconciliationResult>> {
  const res = await fetchWithAuth(`/sessions/${sessionId}/results?page=${page}&limit=${limit}`);
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

