"use client";

import React from "react";
import { WorkflowStep, AsyncStatus, WorkspaceUIState } from "../workspace/types";
import { DataTable, Column } from "@/components/DataTable";
import { Invoice } from "../types";
import { FileUploadStatus } from "../api/reconciliation";
import {
  Database,
  FileSpreadsheet,
  CheckCircle2,
  AlertTriangle,
  LoaderCircle,
  RefreshCw,
  Upload,
  FileText,
  Calendar,
  GitCompareArrows,
} from "lucide-react";

interface PaginationData<T> {
  items: T[];
  totalItems: number | null;
}

interface WorkspaceViewProps {
  type: "sales" | "purchases";
  fromDate: string;
  setFromDate: (v: string) => void;
  toDate: string;
  setToDate: (v: string) => void;
  fileStatuses: FileUploadStatus[];
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  uiState: WorkspaceUIState;
  handleLoadSap: () => void;
  handleFileUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  handleCompare: () => void;
  sapPagination: PaginationData<Invoice>;
  kraPagination: PaginationData<Invoice>;
  workflowStep: WorkflowStep;
  readyToCompare: boolean;
}

const formatVatGroup = (vat?: string) => {
  if (!vat) return "";
  const value = vat.trim();
  return /^\d+(\.\d+)?$/.test(value) ? `${value}%` : value;
};

const invoiceColumns: Column<Invoice>[] = [
  { key: "pin", header: "PIN", accessor: (inv) => <span className="font-mono text-[11px]">{inv.pin || "—"}</span>, skeletonWidth: "w-20" },
  { key: "invNo", header: "Invoice No", accessor: (inv) => <span className="font-mono text-[11px]">{inv.invoice_number}</span>, skeletonWidth: "w-24" },
  { key: "partner", header: "Partner Name", accessor: (inv) => <span className="truncate max-w-[180px] block text-xs" title={inv.partner_name}>{inv.partner_name}</span>, skeletonWidth: "w-32" },
  { key: "date", header: "Invoice Date", accessor: (inv) => <span className="text-xs">{inv.invoice_date}</span>, skeletonWidth: "w-20" },
  { key: "cu", header: "CU Number", accessor: (inv) => <span className="font-mono text-[11px]">{inv.cu_number}</span>, skeletonWidth: "w-32" },
  { key: "base", header: "Base Amount", className: "text-right", accessor: (inv) => <span className="font-mono text-xs">{inv.base_amount.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</span>, skeletonWidth: "w-20" },
  { key: "vat", header: "VAT Group", className: "text-right", accessor: (inv) => <span className="text-xs">{formatVatGroup(inv.vat_group)}</span>, skeletonWidth: "w-12" },
];

const stepConfig = [
  { step: WorkflowStep.LOAD_SAP, label: "Load SAP", shortLabel: "SAP" },
  { step: WorkflowStep.UPLOAD_CSV, label: "Upload KRA CSVs", shortLabel: "KRA" },
  { step: WorkflowStep.COMPARE, label: "Compare & Reconcile", shortLabel: "Compare" },
];

export function WorkspaceView({
  type,
  fromDate, setFromDate,
  toDate, setToDate,
  fileStatuses,
  fileInputRef,
  uiState,
  handleLoadSap,
  handleFileUpload,
  handleCompare,
  sapPagination,
  kraPagination,
  workflowStep,
  readyToCompare,
}: WorkspaceViewProps) {
  const sapLoaded = uiState.sap.status === AsyncStatus.Loaded;
  const kraLoaded = uiState.kra.status === AsyncStatus.Loaded;

  return (
    <div className="flex flex-col gap-3.5 w-full flex-1 min-h-0 overflow-hidden">

      {/* ── Step Progress Tracker ── */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm px-6 py-4">
        <div className="flex items-center gap-0">
          {stepConfig.map(({ step, label }, i) => {
            const done = workflowStep > step;
            const active = workflowStep === step;
            const isLast = i === stepConfig.length - 1;
            return (
              <React.Fragment key={step}>
                <div className="flex items-center gap-2.5 min-w-0">
                  {/* Circle */}
                  <div className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 text-xs font-bold transition-all duration-200 ${done
                    ? "bg-emerald-500 text-white"
                    : active
                      ? "bg-[#0e1734] text-white ring-4 ring-slate-200"
                      : "bg-slate-100 text-slate-400 border border-slate-200"
                    }`}>
                    {done ? <CheckCircle2 className="w-3.5 h-3.5" /> : i + 1}
                  </div>
                  {/* Label */}
                  <span className={`text-xs font-semibold whitespace-nowrap transition-colors ${done ? "text-emerald-600" : active ? "text-[#0e1734]" : "text-slate-400"
                    }`}>
                    {label}
                  </span>
                </div>
                {/* Connector */}
                {!isLast && (
                  <div className={`flex-1 h-px mx-3 rounded-full transition-colors ${workflowStep > step ? "bg-emerald-300" : "bg-slate-200"
                    }`} />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>

      {/* ── Data Source Controls ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

        {/* SAP ERP Data Card */}
        <div className={`bg-white border rounded-xl shadow-sm p-5 flex flex-col gap-4 transition-all duration-200 ${sapLoaded ? "border-slate-300 ring-1 ring-slate-100" : "border-slate-200"
          }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${sapLoaded ? "bg-emerald-500 text-white" : "bg-slate-100 text-slate-500"}`}>
                <Database className="w-4 h-4" />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-900">SAP ERP Data</p>
                <p className="text-[11px] text-slate-400 leading-none mt-0.5">
                  {sapLoaded ? `${sapPagination.totalItems ?? 0} invoices loaded` : "Select date range & load"}
                </p>
              </div>
            </div>
            {sapLoaded && <CheckCircle2 className="w-4.5 h-4.5 text-emerald-500 shrink-0" />}
          </div>

          {/* Quick Period Presets */}
          <div className="flex items-center justify-between pt-1 border-t border-slate-100">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400">Quick Range</span>
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                onClick={() => {
                  const now = new Date();
                  const f = new Date(now.getFullYear(), now.getMonth(), 1).toISOString().split("T")[0];
                  const t = new Date(now.getFullYear(), now.getMonth() + 1, 0).toISOString().split("T")[0];
                  setFromDate(f);
                  setToDate(t);
                }}
                className="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
              >
                This Month
              </button>
              <button
                type="button"
                onClick={() => {
                  const now = new Date();
                  const f = new Date(now.getFullYear(), now.getMonth() - 1, 1).toISOString().split("T")[0];
                  const t = new Date(now.getFullYear(), now.getMonth(), 0).toISOString().split("T")[0];
                  setFromDate(f);
                  setToDate(t);
                }}
                className="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
              >
                Last Month
              </button>
              <button
                type="button"
                onClick={() => {
                  const now = new Date();
                  const f = new Date(now.getFullYear(), 0, 1).toISOString().split("T")[0];
                  const t = now.toISOString().split("T")[0];
                  setFromDate(f);
                  setToDate(t);
                }}
                className="text-[10px] font-medium px-2 py-0.5 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 transition-colors cursor-pointer"
              >
                YTD
              </button>
            </div>
          </div>

          {/* Date Range Inputs Row */}
          <div className="flex items-end gap-3">
            <div className="flex flex-col gap-1 flex-1">
              <label className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1">
                <Calendar className="w-3 h-3 text-slate-400" /> From
              </label>
              <input
                type="date"
                value={fromDate}
                onClick={(e) => {
                  try {
                    (e.currentTarget as HTMLInputElement).showPicker?.();
                  } catch { }
                }}
                onChange={(e) => setFromDate(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs font-mono bg-white hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-colors cursor-pointer [&::-webkit-calendar-picker-indicator]:cursor-pointer [&::-webkit-calendar-picker-indicator]:opacity-60 hover:[&::-webkit-calendar-picker-indicator]:opacity-100"
              />
            </div>
            <div className="flex flex-col gap-1 flex-1">
              <label className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1">
                <Calendar className="w-3 h-3 text-slate-400" /> To
              </label>
              <input
                type="date"
                value={toDate}
                onClick={(e) => {
                  try {
                    (e.currentTarget as HTMLInputElement).showPicker?.();
                  } catch { }
                }}
                onChange={(e) => setToDate(e.target.value)}
                className="w-full px-2.5 py-1.5 border border-slate-200 rounded-lg text-xs font-mono bg-white hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-slate-900/10 focus:border-slate-400 transition-colors cursor-pointer [&::-webkit-calendar-picker-indicator]:cursor-pointer [&::-webkit-calendar-picker-indicator]:opacity-60 hover:[&::-webkit-calendar-picker-indicator]:opacity-100"
              />
            </div>
            <button
              onClick={handleLoadSap}
              disabled={uiState.sap.status === AsyncStatus.Loading}
              className="flex items-center gap-2 px-4 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg text-xs font-semibold transition-all shadow-sm disabled:opacity-50 whitespace-nowrap h-[32px] cursor-pointer shrink-0"
            >
              {uiState.sap.status === AsyncStatus.Loading
                ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" />
                : <RefreshCw className="w-3.5 h-3.5" />}
              {sapLoaded ? "Reload" : "Load SAP"}
            </button>
          </div>
        </div>

        {/* KRA Data Card */}
        <div className={`bg-white border rounded-xl shadow-sm p-5 flex flex-col gap-4 transition-all duration-200 ${kraLoaded ? "border-slate-200 ring-1 ring-slate-100" : "border-slate-200"
          }`}>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${kraLoaded ? "bg-slate-100" : "bg-slate-100"}`}>
                <FileSpreadsheet className={`w-4 h-4 ${kraLoaded ? "text-slate-600" : "text-slate-500"}`} />
              </div>
              <div>
                <p className="text-sm font-semibold text-slate-900">KRA Portal CSVs</p>
                <p className="text-[11px] text-slate-400 leading-none mt-0.5">
                  {kraLoaded
                    ? `${kraPagination.totalItems ?? 0} records from ${fileStatuses.length} file${fileStatuses.length !== 1 ? "s" : ""}`
                    : "No files uploaded"}
                </p>
              </div>
            </div>
            {kraLoaded && <CheckCircle2 className="w-4.5 h-4.5 text-slate-400 shrink-0" />}
          </div>

          {/* Upload Button */}
          <div className="flex flex-col gap-2">
            <input
              type="file"
              multiple
              accept=".csv"
              ref={fileInputRef}
              onChange={handleFileUpload}
              disabled={!sapLoaded || uiState.kra.status === AsyncStatus.Loading}
              className="hidden"
              id="csv-upload"
            />
            <label
              htmlFor="csv-upload"
              className={`inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg text-xs font-semibold border transition-all cursor-pointer h-[34px] w-full ${!sapLoaded
                ? "bg-slate-100 border-slate-200 text-slate-400 cursor-not-allowed"
                : kraLoaded
                  ? "bg-white border-slate-300 text-slate-700 hover:bg-slate-50"
                  : "bg-slate-900 border-transparent text-white hover:bg-slate-800 shadow-sm"
                }`}
            >
              {uiState.kra.status === AsyncStatus.Loading
                ? <LoaderCircle className="w-3.5 h-3.5 animate-spin" />
                : <Upload className="w-3.5 h-3.5" />}
              {kraLoaded ? "Upload More CSVs" : "Upload KRA CSV Files"}
            </label>

            {/* File tags */}
            {fileStatuses.length > 0 && (
              <div className="flex flex-wrap gap-1.5 mt-1">
                {fileStatuses.map((f, idx) => (
                  <div
                    key={idx}
                    className="inline-flex items-center gap-1.5 bg-slate-50 border border-slate-200 rounded-full px-2.5 py-1 text-[11px] font-medium text-slate-700 max-w-[200px]"
                    title={f.filename}
                  >
                    <CheckCircle2 className="w-3 h-3 text-slate-400 shrink-0" />
                    <span className="truncate">{f.filename}</span>
                    <span className="text-slate-500 font-bold shrink-0">·{f.parsed}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── Ready to Compare Banner ── */}
      {readyToCompare && (
        <div className="bg-white rounded-xl p-4 flex items-center justify-between shadow-sm border border-slate-200">
          <div className="flex items-center gap-3">
            <div className="w-9 h-9 rounded-lg bg-slate-100 flex items-center justify-center">
              <GitCompareArrows className="w-5 h-5 text-[#0e1734]" />
            </div>
            <div>
              <p className="text-sm font-bold text-slate-900">Ready to Reconcile</p>
              <p className="text-xs text-slate-500 mt-0.5">
                {sapPagination.totalItems} SAP records · {kraPagination.totalItems} KRA records — click to run comparison
              </p>
            </div>
          </div>
          <button
            onClick={handleCompare}
            disabled={uiState.comparison.status === AsyncStatus.Loading}
            className="flex items-center gap-2 px-5 py-2.5 bg-[#0e1734] text-white hover:bg-[#16224c] active:bg-[#080d21] rounded-lg text-sm font-bold transition-all shadow-sm cursor-pointer disabled:opacity-60 whitespace-nowrap"
          >
            {uiState.comparison.status === AsyncStatus.Loading ? (
              <><LoaderCircle className="w-4 h-4 animate-spin" /> Running...</>
            ) : (
              <><GitCompareArrows className="w-4 h-4" /> Compare & Reconcile</>
            )}
          </button>
        </div>
      )}

      {/* ── Side-by-Side Preview Tables ── */}
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4 flex-1 min-h-0">
        {/* SAP Panel */}
        <div className="flex flex-col bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden h-full">
          <div className="px-4 py-3 border-b border-slate-100 flex justify-between items-center shrink-0">
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-2">
              <Database className="w-3.5 h-3.5 text-slate-400" />
              SAP Data Preview
            </h3>
            {sapLoaded && (
              <span className="text-[11px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                {sapPagination.totalItems} invoices
              </span>
            )}
          </div>
          <div className="flex-1 overflow-hidden relative">
            <DataTable
              data={sapPagination.items}
              columns={invoiceColumns}
              asyncState={uiState.sap}
              emptyState={
                <div className="flex flex-col items-center gap-3 py-12">
                  <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center">
                    <FileText className="w-6 h-6 text-slate-400" strokeWidth={1.5} />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-semibold text-slate-600">No SAP data loaded</p>
                    <p className="text-xs text-slate-400 mt-1">Select a date range and click Load SAP</p>
                  </div>
                </div>
              }
              errorState={
                <div className="flex flex-col items-center gap-3 py-12">
                  <AlertTriangle className="w-8 h-8 text-red-400" strokeWidth={1.5} />
                  <p className="text-sm text-red-600 font-medium">Failed to load SAP invoices</p>
                  <button onClick={handleLoadSap} className="text-xs bg-white border border-slate-300 px-3 py-1.5 rounded-lg hover:bg-slate-50 flex items-center gap-1.5 font-medium">
                    <RefreshCw className="w-3 h-3" /> Retry
                  </button>
                </div>
              }
            />
          </div>
        </div>

        {/* KRA Panel */}
        <div className="flex flex-col bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden h-full">
          <div className="px-4 py-3 border-b border-slate-100 flex justify-between items-center shrink-0">
            <h3 className="text-xs font-bold text-slate-700 uppercase tracking-wider flex items-center gap-2">
              <FileSpreadsheet className="w-3.5 h-3.5 text-slate-400" />
              KRA CSV Preview
            </h3>
            {kraLoaded && (
              <span className="text-[11px] font-semibold text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                {kraPagination.totalItems} records
              </span>
            )}
          </div>
          <div className="flex-1 overflow-hidden relative">
            <DataTable
              data={kraPagination.items}
              columns={invoiceColumns}
              asyncState={uiState.kra}
              emptyState={
                <div className="flex flex-col items-center gap-3 py-12">
                  <div className="w-12 h-12 rounded-xl bg-slate-100 flex items-center justify-center">
                    <FileSpreadsheet className="w-6 h-6 text-slate-400" strokeWidth={1.5} />
                  </div>
                  <div className="text-center">
                    <p className="text-sm font-semibold text-slate-600">No KRA CSVs uploaded</p>
                    <p className="text-xs text-slate-400 mt-1">Load SAP data first, then upload your KRA portal CSV exports</p>
                  </div>
                </div>
              }
              errorState={
                <div className="flex flex-col items-center gap-3 py-12">
                  <AlertTriangle className="w-8 h-8 text-red-400" strokeWidth={1.5} />
                  <p className="text-sm text-red-600 font-medium">Failed to parse KRA CSV</p>
                </div>
              }
            />
          </div>
        </div>
      </div>


    </div>
  );
}
