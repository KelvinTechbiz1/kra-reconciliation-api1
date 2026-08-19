"use client";

import React, { useEffect, useRef, useState, useMemo } from "react";
import { Check, X, AlertTriangle, ArrowUpDown, ArrowUp, ArrowDown, ChevronDown, ChevronRight, Database, FileSpreadsheet, CheckCircle2, Calculator } from "lucide-react";
import { Invoice, ReconciliationResult, ReconciliationSummary } from "../types";
import { RESULT_FILTERS, ResultFilter, ResultSortField, ResultSortOrder } from "@/types";

const formatVatGroup = (vat?: string) => {
  if (!vat) return "";
  const value = vat.trim();
  return /^\d+(\.\d+)?$/.test(value) ? `${value}%` : value;
};

const formatNumeric = (val: string | number | undefined | null) => {
  if (val === null || val === undefined || val === "") return "-";
  if (typeof val === "number" || !isNaN(Number(val))) {
    return Number(val).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
  return String(val);
};

const getTaxBreakdownList = (
  inv: Invoice | Partial<Invoice> | null,
  b16?: number | null,
  b8?: number | null,
  b0?: number | null,
  bExempt?: number | null
) => {
  if (!inv) return [];

  const n16 = b16 != null ? Number(b16) : 0;
  const n8 = b8 != null ? Number(b8) : 0;
  const n0 = b0 != null ? Number(b0) : 0;
  const nExempt = bExempt != null ? Number(bExempt) : 0;

  const hasExplicitBases = (n16 > 0) || (n8 > 0) || (n0 > 0) || (nExempt > 0);

  if (hasExplicitBases) {
    const list: { label: string; amount: number; code: string }[] = [];
    if (n16 > 0) list.push({ label: "16% Standard Rate Base", amount: n16, code: "16%" });
    if (n8 > 0) list.push({ label: "8% Fuel/Reduced Rate Base", amount: n8, code: "8%" });
    if (n0 > 0) list.push({ label: "0% Zero-Rated Base", amount: n0, code: "0%" });
    if (nExempt > 0) list.push({ label: "EXEMPT Base Amount", amount: nExempt, code: "EXEMPT" });
    return list;
  }

  const vatStr = inv.vat_group || "";
  const baseAmt = Number(inv.base_amount || 0);

  return [{
    label: `${formatVatGroup(vatStr) || "16%"} Rate Base`,
    amount: baseAmt,
    code: vatStr || "16%"
  }];
};

interface ResultsTableProps {
  results: ReconciliationResult[];
  summary: ReconciliationSummary | null;
  hasMore?: boolean;
  isLoadingMore?: boolean;
  onLoadMore?: () => void;
  /** Active status filter. Owned by the parent because it is a server query parameter. */
  activeFilter: ResultFilter;
  onFilterChange: (filter: ResultFilter) => void;
  /** Whole-session totals per filter, from the results endpoint. */
  statusCounts: Partial<Record<ResultFilter, number>>;
  /** Active ordering. Also owned by the parent — the server does the sorting. */
  sort: { field: ResultSortField | null; order: ResultSortOrder };
  onSortToggle: (field: ResultSortField) => void;
}



function CompareCell({
  sapVal,
  kraVal,
  isMatch,
  isMissingSap,
  isMissingKra,
  isNumeric = false,
}: {
  sapVal?: string | number;
  kraVal?: string | number;
  isMatch: boolean;
  isMissingSap: boolean;
  isMissingKra: boolean;
  isNumeric?: boolean;
}) {
  const s = isNumeric ? formatNumeric(sapVal) : String(sapVal || "-");
  const k = isNumeric ? formatNumeric(kraVal) : String(kraVal || "-");

  if (isMissingSap) return <span className="text-red-600 font-medium">{k}</span>;
  if (isMissingKra) return <span className="text-red-600 font-medium">{s}</span>;

  if (isMatch) return <span className="text-slate-800">{s}</span>;

  return (
    <div className="flex flex-col text-xs leading-tight">
      <div className="flex items-center justify-between">
        <span className="text-slate-500 w-8">SAP:</span>
        <span className="text-slate-800 font-medium text-right">{s}</span>
      </div>
      <div className="flex items-center justify-between mt-0.5">
        <span className="text-slate-500 w-8">KRA:</span>
        <span className="text-slate-800 font-medium text-right">{k}</span>
      </div>
      <div className="text-amber-600 mt-1 font-medium flex items-center justify-end gap-1">
        <AlertTriangle className="w-3 h-3" />
        Difference
      </div>
    </div>
  );
}

function InformationalCell({
  sapVal,
  kraVal,
  hasDiff,
  isMissingSapRecord,
  isMissingKraRecord,
  isName = false,
}: {
  sapVal?: string;
  kraVal?: string;
  hasDiff: boolean;
  isMissingSapRecord: boolean;
  isMissingKraRecord: boolean;
  isName?: boolean;
}) {
  const s = sapVal?.trim() || "Not available";
  const k = kraVal?.trim() || "Not available";

  if (isMissingSapRecord) return <span className="text-red-600 font-medium truncate block max-w-[150px]" title={k}>{k}</span>;
  if (isMissingKraRecord) return <span className="text-red-600 font-medium truncate block max-w-[150px]" title={s}>{s}</span>;

  if (!hasDiff) {
    const displayVal = sapVal?.trim() ? sapVal.trim() : (kraVal?.trim() || (isName ? "-" : "Not available"));
    return <span className="text-slate-800 truncate block max-w-[150px]" title={displayVal}>{displayVal}</span>;
  }

  return (
    <div className="flex flex-col text-xs leading-tight">
      <div className="flex items-center justify-between">
        <span className="text-slate-500 w-8">SAP:</span>
        <span className="text-slate-800 font-medium text-right truncate max-w-[110px]" title={s}>{s}</span>
      </div>
      <div className="flex items-center justify-between mt-0.5">
        <span className="text-slate-500 w-8">KRA:</span>
        <span className="text-slate-800 font-medium text-right truncate max-w-[110px]" title={k}>{k}</span>
      </div>
      <div className="text-amber-600 mt-1 font-medium flex items-center justify-end gap-1">
        <AlertTriangle className="w-3 h-3" />
        Diff
      </div>
    </div>
  );
}

/** Now that ordering happens server-side, the header shows which way it is sorted
 * rather than a direction-agnostic hint. */
function SortIcon({ active, order }: { active: boolean; order: ResultSortOrder | null }) {
  if (!active) {
    return <ArrowUpDown className="w-3 h-3 text-slate-400 opacity-0 group-hover:opacity-100" />;
  }
  return order === "desc"
    ? <ArrowDown className="w-3 h-3 text-slate-900" />
    : <ArrowUp className="w-3 h-3 text-slate-900" />;
}

export function ResultsTable({
  results,
  summary,
  hasMore = false,
  isLoadingMore = false,
  onLoadMore,
  activeFilter,
  onFilterChange,
  statusCounts,
  sort,
  onSortToggle,
}: ResultsTableProps) {
  const sentinelRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const [expandedRows, setExpandedRows] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!onLoadMore || !hasMore || isLoadingMore) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) onLoadMore();
      },
      { threshold: 0.1, root: containerRef.current }
    );
    const currentSentinel = sentinelRef.current;
    if (currentSentinel) observer.observe(currentSentinel);
    return () => {
      if (currentSentinel) observer.unobserve(currentSentinel);
    };
  }, [onLoadMore, hasMore, isLoadingMore]);

  const handleScroll = (e: React.UIEvent<HTMLDivElement>) => {
    if (!onLoadMore || !hasMore || isLoadingMore) return;
    const { scrollTop, scrollHeight, clientHeight } = e.currentTarget;
    if (scrollHeight - scrollTop - clientHeight < 120) {
      onLoadMore();
    }
  };

  const sortField = sort.field;
  const sortOrder = sort.field ? sort.order : null;
  const toggleSort = onSortToggle;

  const toggleExpand = (id: string) => {
    const newExpanded = new Set(expandedRows);
    if (newExpanded.has(id)) newExpanded.delete(id);
    else newExpanded.add(id);
    setExpandedRows(newExpanded);
  };

  // Built from whole-session counts, so every non-empty group is offered from the
  // first page. Deriving them from `results` meant a chip only appeared once a row of
  // that status had been scrolled into memory.
  // The active filter is always shown even when empty — the KPI cards can select a group
  // with no rows, and dropping its chip would leave the user with no visible way back.
  const availableFilters = useMemo(
    () =>
      RESULT_FILTERS.filter(
        (f) => f === "All" || f === activeFilter || (statusCounts[f] ?? 0) > 0
      ),
    [statusCounts, activeFilter]
  );

  // The server has already applied the filter; these are exactly the rows to show.
  const filteredResults = results;

  // Already ordered by the server; `results` is the page in its final order.
  const sortedResults = filteredResults;

  useEffect(() => {
    if (!onLoadMore || !hasMore || isLoadingMore) return;
    const el = containerRef.current;
    if (el && el.scrollHeight <= el.clientHeight) {
      onLoadMore();
    }
  }, [sortedResults.length, hasMore, isLoadingMore, onLoadMore]);

  // Only bail out when the session genuinely has nothing. An empty page under an active
  // filter must still render the chips, or the user would have no way back to "All".
  const sessionHasResults = (statusCounts.All ?? results.length) > 0;
  if (!sessionHasResults) return null;

  const issuesCount = summary ? summary.total_sap + summary.total_kra - 2 * summary.matches : 0;

  return (
    <div className="flex flex-col">
      {/* Summary KPI Cards - Logo Color Palette */}
      {summary && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          {/* SAP Records Card - Deep Navy Logo Color (#0e1734) */}
          <div 
            onClick={() => onFilterChange("All")}
            className="rounded-xl p-4 transition-all cursor-pointer flex items-center justify-between group shadow-sm bg-gradient-to-br from-[#0e1734] to-[#16295c] text-white border border-[#23356f] hover:scale-[1.01] hover:shadow-md"
          >
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-300">SAP Records</p>
              <p className="text-2xl font-extrabold mt-1 font-mono text-white">{summary.total_sap}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center text-amber-400 group-hover:bg-[#f88602] group-hover:text-white transition-all shadow-2xs">
              <Database className="w-5 h-5" />
            </div>
          </div>

          {/* KRA Records Card - Secondary Slate Navy Logo Tone */}
          <div 
            onClick={() => onFilterChange("All")}
            className="rounded-xl p-4 transition-all cursor-pointer flex items-center justify-between group shadow-sm bg-gradient-to-br from-[#1a274e] to-[#0f1836] text-white border border-[#283b75] hover:scale-[1.01] hover:shadow-md"
          >
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wider text-slate-300">KRA Records</p>
              <p className="text-2xl font-extrabold mt-1 font-mono text-white">{summary.total_kra}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-white/10 flex items-center justify-center text-sky-300 group-hover:bg-sky-500 group-hover:text-white transition-all shadow-2xs">
              <FileSpreadsheet className="w-5 h-5" />
            </div>
          </div>

          {/* Matches Card - Brand Vibrant Orange (#f88602) */}
          <div 
            onClick={() => onFilterChange("Matches")}
            className={`rounded-xl p-4 transition-all cursor-pointer flex items-center justify-between group shadow-sm bg-gradient-to-br from-[#f88602] to-[#d97200] text-white border border-[#ff9d26] ${
              activeFilter === "Matches" ? "ring-2 ring-white shadow-md scale-[1.02]" : "hover:scale-[1.01] hover:shadow-md opacity-95 hover:opacity-100"
            }`}
          >
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wider text-orange-100">Matches</p>
              <p className="text-2xl font-extrabold mt-1 font-mono text-white">{summary.matches}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center text-white group-hover:bg-white group-hover:text-[#f88602] transition-all shadow-2xs">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>

          {/* Issues Card - Dark Red / Crimson Brand Contrast */}
          <div 
            onClick={() => onFilterChange("Issues")}
            className={`rounded-xl p-4 transition-all cursor-pointer flex items-center justify-between group shadow-sm bg-gradient-to-br from-[#85182a] to-[#4d0c17] text-white border border-[#a8253a] ${
              activeFilter === "Issues" ? "ring-2 ring-white shadow-md scale-[1.02]" : "hover:scale-[1.01] hover:shadow-md opacity-95 hover:opacity-100"
            }`}
          >
            <div>
              <p className="text-[11px] font-bold uppercase tracking-wider text-rose-200">Issues</p>
              <p className="text-2xl font-extrabold mt-1 font-mono text-white">{issuesCount}</p>
            </div>
            <div className="w-10 h-10 rounded-xl bg-white/20 flex items-center justify-center text-rose-100 group-hover:bg-white group-hover:text-[#85182a] transition-all shadow-2xs">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
        </div>
      )}

      {/* Segmented Filters */}
      <div className="flex px-2 mb-3">
        <div className="bg-slate-100 p-1 rounded-md flex inline-flex text-sm font-medium">
          {availableFilters.map((f) => (
            <button
              key={f}
              onClick={() => onFilterChange(f)}
              className={`px-3 py-1.5 rounded-md transition-colors cursor-pointer flex items-center gap-1.5 ${activeFilter === f ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900"}`}
            >
              {f}
              {statusCounts[f] !== undefined && (
                <span className={`text-[10px] font-mono ${activeFilter === f ? "text-slate-500" : "text-slate-400"}`}>
                  {statusCounts[f]}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>
      
      <div className="flex flex-col border border-slate-200 bg-white shadow-sm overflow-hidden flex-1 min-h-[400px] max-h-[calc(100vh-250px)] rounded-md">
        <div ref={containerRef} onScroll={handleScroll} className="overflow-auto flex-1 relative">
          <table className="w-full text-sm text-left whitespace-nowrap">
            <thead className="bg-slate-50 text-slate-600 text-xs tracking-wider border-b border-slate-200 sticky top-0 z-20 shadow-sm">
              <tr>
                <th className="px-3 py-3 font-medium w-8 text-center bg-slate-50"></th>
                <th className="px-2 py-3 font-medium w-8 text-center bg-slate-50"></th>
                <th className="px-4 py-3 font-medium bg-slate-50 cursor-pointer select-none group" onClick={() => toggleSort("pin")}>
                  <div className="flex items-center gap-1">PIN <SortIcon active={sortField === "pin"} order={sortOrder} /></div>
                </th>
                <th className="px-4 py-3 font-medium bg-slate-50 cursor-pointer select-none group" onClick={() => toggleSort("invoice_number")}>
                  <div className="flex items-center gap-1">Invoice No <SortIcon active={sortField === "invoice_number"} order={sortOrder} /></div>
                </th>
                <th className="px-4 py-3 font-medium bg-slate-50">Partner Name</th>
                <th className="px-4 py-3 font-medium bg-slate-50 cursor-pointer select-none group" onClick={() => toggleSort("invoice_date")}>
                  <div className="flex items-center gap-1">Invoice Date <SortIcon active={sortField === "invoice_date"} order={sortOrder} /></div>
                </th>
                <th className="px-4 py-3 font-medium bg-slate-50">CU Number</th>
                <th className="px-4 py-3 font-medium text-right bg-slate-50 cursor-pointer select-none group" onClick={() => toggleSort("base_amount")}>
                  <div className="flex items-center justify-end gap-1">Base Amount <SortIcon active={sortField === "base_amount"} order={sortOrder} /></div>
                </th>
                <th className="px-4 py-3 font-medium text-right bg-slate-50 cursor-pointer select-none group" onClick={() => toggleSort("vat_group")}>
                  <div className="flex items-center justify-end gap-1">VAT Group <SortIcon active={sortField === "vat_group"} order={sortOrder} /></div>
                </th>
                <th className="px-4 py-3 font-medium bg-slate-50 cursor-pointer select-none group" onClick={() => toggleSort("status")}>
                  <div className="flex items-center gap-1">Remark <SortIcon active={sortField === "status"} order={sortOrder} /></div>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {sortedResults.map((r, idx) => {
                const isMatch = r.status === "Match" || r.status === "Matched" || r.status === "MATCH";
                const isMissingSap = r.status === "Missing in SAP" || r.status === "MISSING_IN_SAP";
                const isMissingKra = r.status === "Missing in KRA" || r.status === "MISSING_IN_KRA";
                const isMissingCu = r.status === "Missing CU Number" || r.status === "MISSING_CU_NUMBER";
                
                const sap = r.sap || {} as Partial<Invoice>;
                const kra = r.kra || {} as Partial<Invoice>;
                const rowId = `${r.cu_number}-${idx}`;
                const isExpanded = expandedRows.has(rowId);

                let remark = r.status;
                let remarkColor = "text-slate-600";
                
                if (isMatch) {
                  remark = "Match";
                  remarkColor = "text-green-600";
                } else if (isMissingCu) {
                  remark = "Missing CU Number";
                  remarkColor = "text-purple-600";
                } else if (isMissingSap) {
                  remark = "Missing in SAP";
                  remarkColor = "text-red-600";
                } else if (isMissingKra) {
                  remark = "Missing in KRA";
                  remarkColor = "text-red-600";
                } else {
                  remarkColor = "text-amber-600";
                  if (r.status === "AMOUNT_MISMATCH") remark = "Amount Mismatch";
                  else if (r.status === "VAT_MISMATCH") remark = "VAT Mismatch";
                  else if (r.status === "CU_MISMATCH" || r.status === "CU Mismatch") remark = "CU Mismatch";
                  else if (r.status === "PIN_MISMATCH" || r.status === "PIN Mismatch") remark = "PIN Mismatch";
                  else if (r.status === "DATE_MISMATCH") remark = "Date Mismatch";
                  else if (r.status === "MULTIPLE_MISMATCHES") remark = "Multiple Mismatches";
                  else if (r.status === "DUPLICATE_SOURCE_KEY") remark = "Duplicate MatchKey";
                }

                const pinHasDiff = !r.pin_matches;
                const nameHasDiff = !r.partner_name_matches;

                return (
                  <React.Fragment key={rowId}>
                    <tr 
                      className={`hover:bg-slate-50 transition-colors cursor-pointer ${isExpanded ? "bg-slate-50" : "bg-white"}`}
                      onClick={() => toggleExpand(rowId)}
                    >
                      <td className="px-3 py-2 text-center align-middle">
                        <button className="text-slate-400 hover:text-slate-600 focus:outline-none">
                          {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                        </button>
                      </td>
                      <td className="px-2 py-2 text-center align-middle">
                        {isMatch ? (
                          <Check className="w-4 h-4 text-green-600 inline-block" strokeWidth={3} />
                        ) : isMissingSap || isMissingKra ? (
                          <X className="w-4 h-4 text-red-600 inline-block" strokeWidth={3} />
                        ) : (
                          <AlertTriangle className="w-4 h-4 text-amber-500 inline-block" strokeWidth={2.5} />
                        )}
                      </td>
                      
                      <td className="px-4 py-2 font-mono align-middle">
                        <InformationalCell sapVal={sap.pin} kraVal={kra.pin} hasDiff={pinHasDiff} isMissingSapRecord={isMissingSap} isMissingKraRecord={isMissingKra} />
                      </td>
                      
                      <td className="px-4 py-2 font-mono align-middle">
                        <CompareCell sapVal={sap.invoice_number} kraVal={kra.invoice_number} isMatch={true} isMissingSap={isMissingSap} isMissingKra={isMissingKra} />
                      </td>
                      
                      <td className="px-4 py-2 align-middle">
                        <InformationalCell sapVal={sap.partner_name} kraVal={kra.partner_name} hasDiff={nameHasDiff} isMissingSapRecord={isMissingSap} isMissingKraRecord={isMissingKra} isName={true} />
                      </td>
                      
                      <td className="px-4 py-2 align-middle font-mono">
                        <CompareCell sapVal={sap.invoice_date} kraVal={kra.invoice_date} isMatch={r.date_match ?? isMatch} isMissingSap={isMissingSap} isMissingKra={isMissingKra} />
                      </td>
                      
                      <td className="px-4 py-2 font-mono text-slate-500 align-middle">
                        {r.cu_number || "-"}
                      </td>
                      
                      <td className="px-4 py-2 text-right font-mono align-middle">
                        <CompareCell sapVal={sap.base_amount} kraVal={kra.base_amount} isMatch={r.amount_match ?? isMatch} isMissingSap={isMissingSap} isMissingKra={isMissingKra} isNumeric={true} />
                      </td>
                      
                      <td className="px-4 py-2 text-right align-middle font-mono">
                        <CompareCell sapVal={formatVatGroup(sap.vat_group)} kraVal={formatVatGroup(kra.vat_group)} isMatch={r.vat_match ?? isMatch} isMissingSap={isMissingSap} isMissingKra={isMissingKra} />
                      </td>
                      
                      <td className={`px-4 py-2 font-medium align-middle ${remarkColor}`}>
                        {remark}
                      </td>
                    </tr>

                    {/* Expandable Details Grid */}
                    {isExpanded && (
                      <tr className="bg-slate-50 border-b border-slate-200 shadow-inner">
                        <td colSpan={10} className="p-0">
                          <div className="px-10 py-6 border-x border-slate-200 mx-4 my-2 bg-white rounded-md shadow-sm">
                            <div className="mb-4 pb-2 border-b border-slate-100 flex items-center justify-between">
                              <h4 className="font-semibold text-slate-800 flex items-center gap-2">
                                Reconciliation Details
                              </h4>
                              <span className={`px-2.5 py-1 rounded-md text-xs font-semibold ${
                                isMatch ? "bg-green-100 text-green-700" :
                                isMissingSap || isMissingKra ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-800"
                              }`}>
                                Status: {remark}
                              </span>
                            </div>
                            
                            <table className="w-full text-sm border-collapse">
                              <thead>
                                <tr className="text-left text-slate-500 border-b border-slate-200">
                                  <th className="font-medium py-2 w-1/4">Field</th>
                                  <th className="font-medium py-2 w-1/3">SAP</th>
                                  <th className="font-medium py-2 w-1/3">KRA</th>
                                </tr>
                              </thead>
                              <tbody className="divide-y divide-slate-100">
                                {["PIN", "Invoice No", "Partner Name", "Invoice Date", "CU Number", "VAT Group", "Base Amount"].map((field) => {
                                  let sVal: string | number | undefined | null = "-"; let kVal: string | number | undefined | null = "-";
                                  let isFieldMatch = false;
                                  
                                  if (field === "PIN") { sVal = sap.pin?.trim() || "Not available"; kVal = kra.pin?.trim() || "Not available"; isFieldMatch = !pinHasDiff; }
                                  if (field === "Invoice No") { sVal = sap.invoice_number; kVal = kra.invoice_number; isFieldMatch = true; }
                                  if (field === "Partner Name") { sVal = sap.partner_name?.trim() || "Not available"; kVal = kra.partner_name?.trim() || "Not available"; isFieldMatch = !nameHasDiff; }
                                  if (field === "Invoice Date") { sVal = sap.invoice_date; kVal = kra.invoice_date; isFieldMatch = r.date_match ?? (sVal === kVal); }
                                  if (field === "CU Number") { sVal = sap.cu_number; kVal = kra.cu_number; isFieldMatch = sVal?.trim() === kVal?.trim(); }
                                  if (field === "VAT Group") { sVal = formatVatGroup(sap.vat_group); kVal = formatVatGroup(kra.vat_group); isFieldMatch = r.vat_match ?? (sVal === kVal); }
                                  if (field === "Base Amount") { sVal = sap.base_amount; kVal = kra.base_amount; isFieldMatch = r.amount_match ?? (sVal === kVal); }

                                  // Skip rows where both are null/empty
                                  if (!sVal && !kVal) return null;

                                  const highlightClass = !isFieldMatch && !isMissingSap && !isMissingKra ? "bg-amber-50" : "";
                                  const textClass = !isFieldMatch && !isMissingSap && !isMissingKra ? "text-amber-800 font-medium" : "text-slate-700";

                                  return (
                                    <tr key={field} className={highlightClass}>
                                      <td className="py-2.5 font-medium text-slate-600 px-2">{field}</td>
                                      <td className={`py-2.5 font-mono px-2 ${!sVal && isMissingSap ? "text-red-500 italic" : textClass}`}>
                                        {field.includes("Amount") ? formatNumeric(sVal) : String(sVal || "-")}
                                      </td>
                                      <td className={`py-2.5 font-mono px-2 ${!kVal && isMissingKra ? "text-red-500 italic" : textClass}`}>
                                        {field.includes("Amount") ? formatNumeric(kVal) : String(kVal || "-")}
                                      </td>
                                    </tr>
                                  );
                                })}
                              </tbody>
                            </table>

                            {/* Itemized VAT Category Base Accumulation Card */}
                            <div className="mt-5 pt-4 border-t border-slate-200">
                              <div className="flex items-center justify-between mb-3">
                                <h5 className="text-xs font-bold uppercase tracking-wider text-slate-600 flex items-center gap-1.5">
                                  <Calculator className="w-4 h-4 text-emerald-600" />
                                  Itemized VAT Category Base Accumulation
                                </h5>
                              </div>

                              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs">
                                {/* SAP (ERP) Breakdown */}
                                <div className="p-3 bg-slate-50/80 rounded-lg border border-slate-200">
                                  <div className="flex items-center justify-between font-semibold text-slate-700 pb-2 mb-2 border-b border-slate-200">
                                    <span className="flex items-center gap-1.5">
                                      <Database className="w-3.5 h-3.5 text-slate-500" />
                                      SAP Base Accumulation
                                    </span>
                                    <span className="font-mono text-slate-900 font-bold">
                                      KES {formatNumeric(sap.base_amount)}
                                    </span>
                                  </div>
                                  
                                  {isMissingSap ? (
                                    <p className="text-red-500 italic py-1 text-center">Document missing in SAP</p>
                                  ) : (
                                    <div className="space-y-1.5">
                                      {getTaxBreakdownList(sap, r.sap_base_16, r.sap_base_8, r.sap_base_0, r.sap_base_exempt).map((item, i) => (
                                        <div key={i} className="flex items-center justify-between bg-white px-2.5 py-1.5 rounded border border-slate-200 shadow-2xs">
                                          <span className="text-slate-600 font-medium">{item.label}</span>
                                          <span className="font-mono font-bold text-slate-800">{formatNumeric(item.amount)}</span>
                                        </div>
                                      ))}
                                      <div className="pt-2 flex items-center justify-between text-slate-700 font-medium text-[11px] border-t border-dashed border-slate-300">
                                        <span>= Total Accumulated SAP Base</span>
                                        <span className="font-mono font-bold text-slate-900">KES {formatNumeric(sap.base_amount)}</span>
                                      </div>
                                    </div>
                                  )}
                                </div>

                                {/* KRA (eTIMS) Breakdown */}
                                <div className="p-3 bg-slate-50/80 rounded-lg border border-slate-200">
                                  <div className="flex items-center justify-between font-semibold text-slate-700 pb-2 mb-2 border-b border-slate-200">
                                    <span className="flex items-center gap-1.5">
                                      <FileSpreadsheet className="w-3.5 h-3.5 text-slate-500" />
                                      KRA Base Accumulation
                                    </span>
                                    <span className="font-mono text-slate-900 font-bold">
                                      KES {formatNumeric(kra.base_amount)}
                                    </span>
                                  </div>

                                  {isMissingKra ? (
                                    <p className="text-red-500 italic py-1 text-center">Document missing in KRA</p>
                                  ) : (
                                    <div className="space-y-1.5">
                                      {getTaxBreakdownList(kra, r.kra_base_16, r.kra_base_8, r.kra_base_0, r.kra_base_exempt).map((item, i) => (
                                        <div key={i} className="flex items-center justify-between bg-white px-2.5 py-1.5 rounded border border-slate-200 shadow-2xs">
                                          <span className="text-slate-600 font-medium">{item.label}</span>
                                          <span className="font-mono font-bold text-slate-800">{formatNumeric(item.amount)}</span>
                                        </div>
                                      ))}
                                      <div className="pt-2 flex items-center justify-between text-slate-700 font-medium text-[11px] border-t border-dashed border-slate-300">
                                        <span>= Total Accumulated KRA Base</span>
                                        <span className="font-mono font-bold text-slate-900">KES {formatNumeric(kra.base_amount)}</span>
                                      </div>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* Show Numeric Difference for Amounts */}
                            {(!isMatch && !isMissingSap && !isMissingKra) && (
                              <div className="mt-4 pt-3 border-t border-slate-200 text-sm">
                                {sap.base_amount !== kra.base_amount && (
                                  <div className="flex items-center gap-2 text-amber-700 font-medium px-2">
                                    <AlertTriangle className="w-4 h-4" />
                                    <span>Base Amount differs by KES {formatNumeric(Math.abs(Number(sap.base_amount || 0) - Number(kra.base_amount || 0)))}</span>
                                  </div>
                                )}
                              </div>
                            )}

                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                );
              })}

              {/* Skeleton Loader Rows */}
              {isLoadingMore && (
                <>
                  {[...Array(3)].map((_, i) => (
                    <tr key={`skeleton-${i}`} className="animate-pulse bg-white border-b border-slate-100">
                      <td className="px-3 py-3"><div className="h-4 bg-slate-100 rounded w-4 mx-auto"></div></td>
                      <td className="px-2 py-3"><div className="h-4 bg-slate-100 rounded w-4 mx-auto"></div></td>
                      <td className="px-4 py-3"><div className="h-4 bg-slate-100 rounded w-20"></div></td>
                      <td className="px-4 py-3"><div className="h-4 bg-slate-100 rounded w-24"></div></td>
                      <td className="px-4 py-3"><div className="h-4 bg-slate-100 rounded w-32"></div></td>
                      <td className="px-4 py-3"><div className="h-4 bg-slate-100 rounded w-20"></div></td>
                      <td className="px-4 py-3"><div className="h-4 bg-slate-100 rounded w-28"></div></td>
                      <td className="px-4 py-3"><div className="h-4 bg-slate-100 rounded w-16 ml-auto"></div></td>
                      <td className="px-4 py-3"><div className="h-4 bg-slate-100 rounded w-10 ml-auto"></div></td>
                      <td className="px-4 py-3"><div className="h-4 bg-slate-100 rounded w-24"></div></td>
                    </tr>
                  ))}
                </>
              )}
              {sortedResults.length === 0 && (
                <tr>
                  <td colSpan={10} className="px-4 py-16 text-center text-sm text-slate-500">
                    {isLoadingMore ? (
                      <span>Loading {activeFilter === "All" ? "results" : activeFilter}…</span>
                    ) : (
                      <span>
                        No rows under <span className="font-semibold text-slate-700">{activeFilter}</span>.
                      </span>
                    )}
                  </td>
                </tr>
              )}
            </tbody>
          </table>

          {/* Intersection Sentinel element */}
          {hasMore && <div ref={sentinelRef} className="h-4 w-full" />}
        </div>
      </div>
    </div>
  );
}
