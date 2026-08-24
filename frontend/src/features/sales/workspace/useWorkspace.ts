import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useToast } from "@/components/ToastProvider";
import { usePagination } from "@/hooks/usePagination";
import { Invoice, ReconciliationResult, ReconciliationSummary } from "../types";
import {
  fetchInvoicesPreview,
  uploadInvoicesCSV,
  removeKraFile,
  uploadErpInvoices,
  compareInvoices,
  fetchInvoicesPage,
  fetchReconciliationResultsPage,
  FileUploadStatus
} from "../api/reconciliation";
import { AsyncStatus, WorkspaceUIState } from "./types";
import { ResultFilter, ResultSortField, ResultSortOrder } from "@/types";
import { getWorkflowStep, getSessionStatus, isReadyToCompare, getMetrics } from "./selectors";

export function useWorkspace(type: "sales" | "purchases") {
  const router = useRouter();
  const { notify } = useToast();
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [fileStatuses, setFileStatuses] = useState<FileUploadStatus[]>([]);
  // Filenames with a delete in flight, so their tag can show a spinner and refuse a
  // second click.
  const [removingFiles, setRemovingFiles] = useState<string[]>([]);
  
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  
  // UI State single source of truth
  const [uiState, setUiState] = useState<WorkspaceUIState>({
    sap: { status: AsyncStatus.Idle },
    kra: { status: AsyncStatus.Idle },
    comparison: { status: AsyncStatus.Idle }
  });

  const [summary, setSummary] = useState<ReconciliationSummary | null>(null);
  const [globalError, setGlobalError] = useState<string | null>(null);

  // Paginated Fetchers
  const fetchSapPage = useCallback((page: number, limit: number) => {
    if (!sessionId) return Promise.reject("No active session");
    return fetchInvoicesPage(sessionId, "SAP", page, limit);
  }, [sessionId]);

  const fetchKraPage = useCallback((page: number, limit: number) => {
    if (!sessionId) return Promise.reject("No active session");
    return fetchInvoicesPage(sessionId, "KRA", page, limit);
  }, [sessionId]);

  // Which status group the results table is showing. Held here rather than inside the
  // table because it is a query parameter: changing it refetches from page 1 instead of
  // narrowing whatever happens to be in memory.
  const [resultsFilter, setResultsFilter] = useState<ResultFilter>("All");
  const [resultStatusCounts, setResultStatusCounts] = useState<Partial<Record<ResultFilter, number>>>({});
  // Sort lives here for the same reason the filter does: it orders the whole session in
  // SQL, not just the rows infinite scroll happens to have fetched.
  const [resultsSort, setResultsSort] = useState<{ field: ResultSortField | null; order: ResultSortOrder }>({
    field: null,
    order: "asc",
  });

  const fetchResultsPage = useCallback(async (page: number, limit: number) => {
    if (!sessionId) return Promise.reject("No active session");
    const res = await fetchReconciliationResultsPage(
      sessionId, page, limit, resultsFilter, resultsSort.field, resultsSort.order
    );
    // Counts describe the whole session, so they only need writing when they actually
    // change — not on every page of an infinite scroll.
    setResultStatusCounts((prev) =>
      JSON.stringify(prev) === JSON.stringify(res.status_counts) ? prev : res.status_counts
    );
    return res;
  }, [sessionId, resultsFilter, resultsSort]);

  // Hook Instantiations
  const sapPagination = usePagination<Invoice>(fetchSapPage, { limit: 100, enabled: false });
  const kraPagination = usePagination<Invoice>(fetchKraPage, { limit: 100, enabled: false });
  const resultsPagination = usePagination<ReconciliationResult>(fetchResultsPage, {
    limit: 100,
    enabled: uiState.comparison.status === AsyncStatus.Loaded && !!sessionId,
  });

  const handleLoadSap = async () => {
    if (!fromDate || !toDate) {
      setGlobalError("Please select both From and To dates.");
      return;
    }
    
    setUiState(prev => ({
      ...prev,
      sap: { status: AsyncStatus.Loading },
      kra: { status: AsyncStatus.Idle },
      comparison: { status: AsyncStatus.Idle }
    }));
    setGlobalError(null);
    setSummary(null);
    sapPagination.reset();
    kraPagination.reset();
    resultsPagination.reset();
    setResultsFilter("All");
    setResultStatusCounts({});
    setResultsSort({ field: null, order: "asc" });
    setFileStatuses([]);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }

    try {
      const data = await fetchInvoicesPreview(type, fromDate, toDate);
      setSessionId(data.session_id);
      
      const totalPages = Math.ceil(data.count / 100);
      sapPagination.reset(data.invoices, data.count, totalPages);
      
      setUiState(prev => ({ ...prev, sap: { status: AsyncStatus.Loaded } }));
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "An unknown error occurred loading SAP data.";

      const upper = errorMessage.toUpperCase();
      if (
        upper.includes("NO SAP CONNECTION CONFIGURED") ||
        upper.includes("NOT ASSOCIATED WITH A COMPANY")
      ) {
        notify(
          "No SAP connection is configured for your company. Add one in Settings to fetch data.",
          "error"
        );
        router.push("/settings");
        return;
      }

      setUiState(prev => ({ ...prev, sap: { status: AsyncStatus.Error, error: errorMessage } }));
    }
  };

  const handleLoadErpFile = async (files: File[], profileId?: number | null) => {
    if (files.length === 0) return;

    setUiState(prev => ({
      ...prev,
      sap: { status: AsyncStatus.Loading },
      kra: { status: AsyncStatus.Idle },
      comparison: { status: AsyncStatus.Idle }
    }));
    setGlobalError(null);
    setSummary(null);
    sapPagination.reset();
    kraPagination.reset();
    resultsPagination.reset();
    setFileStatuses([]);

    try {
      const data = await uploadErpInvoices(type, files, profileId, sessionId);
      setSessionId(data.session_id);

      const totalPages = Math.ceil(data.count / 100);
      sapPagination.reset(data.invoices, data.count, totalPages);

      setUiState(prev => ({ ...prev, sap: { status: AsyncStatus.Loaded } }));
      notify(`Loaded ${data.count} ERP invoices using profile "${data.profile_name || "Default"}"`, "success");
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "An error occurred uploading ERP file.";
      setUiState(prev => ({ ...prev, sap: { status: AsyncStatus.Error, error: errorMessage } }));
    }
  };


  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(e.target.files || []);
    if (files.length === 0) return;
    if (!sessionId) {
      setGlobalError("Please load ERP or SAP data first to create a session.");
      return;
    }

    setUiState(prev => ({
      ...prev,
      kra: { status: AsyncStatus.Loading },
      comparison: { status: AsyncStatus.Idle }
    }));
    setGlobalError(null);
    setSummary(null);
    resultsPagination.reset();

    try {
      const data = await uploadInvoicesCSV(type, sessionId, files);
      // Uploads append server-side, so keep the tags from earlier passes. Re-uploading
      // a file replaces its own tag rather than showing it twice.
      setFileStatuses(prev => [
        ...prev.filter(p => !data.files.some(f => f.filename === p.filename)),
        ...data.files,
      ]);

      // Re-read page 1 from the session rather than seeding it with just-uploaded rows:
      // an append leaves earlier sections ahead of these in the preview.
      try {
        const firstPage = await fetchKraPage(1, 100);
        kraPagination.reset(firstPage.items, firstPage.total, firstPage.total_pages);
      } catch {
        const totalParsed = data.total_kra_records;
        kraPagination.reset(data.invoices, totalParsed, Math.ceil(totalParsed / 100));
      }

      setUiState(prev => ({ ...prev, kra: { status: AsyncStatus.Loaded } }));
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "An unknown error occurred uploading CSV.";
      setUiState(prev => ({ ...prev, kra: { status: AsyncStatus.Error, error: errorMessage } }));
    } finally {
      // Always clear, so selecting the same files again re-fires onChange. Previously
      // this only ran on failure and a repeat selection did nothing at all.
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  // Undo one upload. Uploading the wrong CSV used to mean reloading the page and
  // re-fetching SAP, because uploads append and nothing could take a single file back out.
  const handleRemoveKraFile = async (filename: string) => {
    if (!sessionId || removingFiles.includes(filename)) return;

    setRemovingFiles(prev => [...prev, filename]);
    setGlobalError(null);

    try {
      const res = await removeKraFile(type, sessionId, filename);

      setFileStatuses(prev => prev.filter(f => f.filename !== filename));

      // The removed rows may have taken part in a comparison, which the server has just
      // invalidated. Drop what the results view is holding rather than leave it showing
      // totals for rows that no longer exist.
      setSummary(null);
      resultsPagination.reset();
      setResultsFilter("All");
      setResultStatusCounts({});
      setResultsSort({ field: null, order: "asc" });

      if (res.total_kra_records === 0) {
        kraPagination.reset();
        setUiState(prev => ({
          ...prev,
          kra: { status: AsyncStatus.Idle },
          comparison: { status: AsyncStatus.Idle },
        }));
      } else {
        const firstPage = await fetchKraPage(1, 100);
        kraPagination.reset(firstPage.items, firstPage.total, firstPage.total_pages);
        setUiState(prev => ({
          ...prev,
          kra: { status: AsyncStatus.Loaded },
          comparison: { status: AsyncStatus.Idle },
        }));
      }

      notify(`Removed ${filename}`, "success");
    } catch (err: unknown) {
      // The tag stays put on failure — the rows are still in the session.
      notify(
        err instanceof Error ? err.message : `Failed to remove ${filename}`,
        "error"
      );
    } finally {
      setRemovingFiles(prev => prev.filter(f => f !== filename));
    }
  };

  const handleCompare = async (): Promise<boolean> => {
    if (!sessionId) return false;
    
    setUiState(prev => ({ ...prev, comparison: { status: AsyncStatus.Loading } }));
    setGlobalError(null);
    resultsPagination.reset();
    setResultsFilter("All");
    setResultStatusCounts({});
    setResultsSort({ field: null, order: "asc" });

    try {
      const data = await compareInvoices(sessionId);
      setSummary(data.summary);
      setUiState(prev => ({ ...prev, comparison: { status: AsyncStatus.Loaded } }));
      return true;
    } catch (err: unknown) {
      const errorMessage = err instanceof Error ? err.message : "An unknown error occurred during comparison.";

      const upper = errorMessage.toUpperCase();
      if (upper.includes("INVOICE LOAD IS REQUIRED")) {
        setUiState(prev => ({ ...prev, comparison: { status: AsyncStatus.Empty, emptyReason: "SAP" } }));
        return true;
      }
      if (upper.includes("KRA CSV UPLOAD IS REQUIRED")) {
        setUiState(prev => ({ ...prev, comparison: { status: AsyncStatus.Empty, emptyReason: "KRA" } }));
        return true;
      }

      setUiState(prev => ({ ...prev, comparison: { status: AsyncStatus.Error, error: errorMessage } }));
      setGlobalError(errorMessage);
      return false;
    }
  };

  const resetState = () => {
    setSessionId(null);
    setUiState({
      sap: { status: AsyncStatus.Idle },
      kra: { status: AsyncStatus.Idle },
      comparison: { status: AsyncStatus.Idle }
    });
    setSummary(null);
    sapPagination.reset();
    kraPagination.reset();
    resultsPagination.reset();
    setFileStatuses([]);
    setRemovingFiles([]);
    setFromDate("");
    setToDate("");
    setGlobalError(null);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // asc -> desc -> unsorted, the cycle the column headers already implied.
  const toggleResultsSort = useCallback((field: ResultSortField) => {
    setResultsSort((prev) => {
      if (prev.field !== field) return { field, order: "asc" };
      if (prev.order === "asc") return { field, order: "desc" };
      return { field: null, order: "asc" };
    });
  }, []);

  // Derived Values
  const workflowStep = getWorkflowStep(uiState);
  const sessionStatus = getSessionStatus(uiState);
  const readyToCompare = isReadyToCompare(uiState);
  const metrics = getMetrics(
    uiState, 
    sapPagination.totalItems || 0, 
    kraPagination.totalItems || 0,
    summary?.matches,
    summary?.mismatches
  );

  return {
    fromDate,
    toDate,
    setFromDate,
    setToDate,
    fileStatuses,
    fileInputRef,
    sessionId,
    uiState,
    summary,
    globalError,
    resultsFilter,
    setResultsFilter,
    resultStatusCounts,
    resultsSort,
    toggleResultsSort,
    setGlobalError,
    handleLoadSap,
    handleLoadErpFile,
    handleFileUpload,
    handleRemoveKraFile,
    removingFiles,
    handleCompare,
    resetState,

    sapPagination,
    kraPagination,
    resultsPagination,
    
    // Derived UI states
    workflowStep,
    sessionStatus,
    readyToCompare,
    metrics
  };
}
