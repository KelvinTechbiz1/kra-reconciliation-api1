"use client";

import React, { useState } from "react";
import { ReconciliationResult, ReconciliationSummary } from "../types";
import { ResultsTable } from "./ResultsTable";
import { Download, ArrowLeft, AlertTriangle, Inbox } from "lucide-react";
import { exportReconciliationZip } from "../api/exportApi";
import { AsyncStatus } from "../workspace/types";

interface ReconciliationResultsViewProps {
  sessionId: string;
  type: "sales" | "purchases";
  summary: ReconciliationSummary | null;
  resultsPagination: {
    items: ReconciliationResult[];
    hasMore: boolean;
    isLoadingMore: boolean;
    isInitialLoading: boolean;
    loadNextPage: () => void;
  };
  comparisonStatus?: AsyncStatus;
  emptyReason?: "SAP" | "KRA";
  onBack: () => void;
}

export function ReconciliationResultsView({ 
  sessionId, 
  type, 
  summary, 
  resultsPagination, 
  comparisonStatus,
  emptyReason,
  onBack 
}: ReconciliationResultsViewProps) {
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [mounted, setMounted] = useState(false);

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);

  const handleExport = async () => {
    setExporting(true);
    setExportError(null);
    try {
      await exportReconciliationZip(type, sessionId);
    } catch (err: unknown) {
      if (err instanceof Error) {
        setExportError(err.message);
      } else {
        setExportError("Export failed");
      }
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 w-full h-full min-h-0 flex-1 overflow-hidden animate-fade-in">
      <div className="flex items-center justify-between bg-white p-4 rounded-lg border border-slate-200 shadow-sm">
        <div className="flex items-center gap-6">
          <button 
            onClick={onBack}
            className="text-slate-600 hover:text-slate-900 text-sm font-semibold flex items-center gap-2 transition-colors px-3 py-1.5 rounded-md hover:bg-slate-50"
          >
            <ArrowLeft className="w-4 h-4" />
            Back to Workspace
          </button>
          <div className="h-4 w-px bg-slate-300"></div>
          <span className="text-sm font-medium text-slate-500">
            {mounted ? `Completed ${new Date().toLocaleString('en-GB', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' })}` : "Completed"}
          </span>
        </div>
        
        <button
          onClick={handleExport}
          disabled={exporting}
          className="bg-emerald-600 text-white px-5 py-2 rounded-md font-medium text-sm hover:bg-emerald-700 transition-colors disabled:opacity-50 flex items-center gap-2"
        >
          {exporting ? (
            <>
              <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
              Exporting...
            </>
          ) : (
            <>
              <Download className="w-4 h-4" />
              Export ZIP
            </>
          )}
        </button>
      </div>

      {exportError && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-md text-sm shadow-sm flex items-center gap-2 animate-shake">
          <AlertTriangle className="w-4 h-4" />
          {exportError}
        </div>
      )}

      {comparisonStatus === AsyncStatus.Empty ? (
        <div className="bg-white rounded-lg shadow-sm border border-slate-200 p-10 text-center">
          <div className="flex flex-col items-center gap-3 text-slate-500">
            <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center">
              <Inbox className="w-6 h-6 text-slate-400" />
            </div>
            <h3 className="text-base font-semibold text-slate-700">
              {emptyReason === "SAP"
                ? "No ERP / SAP invoices to compare"
                : "No KRA invoices to compare"}
            </h3>
            <p className="text-sm max-w-md">
              {emptyReason === "SAP"
                ? "No ERP or SAP invoices were loaded for this session. Load ERP or SAP data first, then upload the matching KRA CSV before comparing."
                : "No KRA CSV has been uploaded for this session. Upload the KRA CSV file, then run the comparison again."}
            </p>
            <button
              onClick={onBack}
              className="mt-2 text-[#0e1734] hover:text-[#16224c] font-semibold text-sm cursor-pointer"
            >
              Return to Workspace
            </button>
          </div>
        </div>
      ) : (
        <div className="flex-1 min-h-0 flex flex-col">
          <ResultsTable 
            results={resultsPagination.items} 
            summary={summary} 
            hasMore={resultsPagination.hasMore}
            isLoadingMore={resultsPagination.isLoadingMore || resultsPagination.isInitialLoading}
            onLoadMore={resultsPagination.loadNextPage}
          />
        </div>
      )}
    </div>
  );
}
