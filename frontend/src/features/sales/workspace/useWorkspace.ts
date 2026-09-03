import { useState, useRef, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useToast } from "@/components/ToastProvider";
import { usePagination } from "@/hooks/usePagination";
import { Invoice, ReconciliationResult, ReconciliationSummary } from "../types";
import {
  fetchInvoicesPreview,
  splitDateRange,
  uploadInvoicesCSV,
  removeKraFile,
  uploadErpInvoices,
  compareInvoices,
  fetchInvoicesPage,
  fetchReconciliationResultsPage,
  KraFileTag
} from "../api/reconciliation";
import { AsyncStatus, WorkspaceUIState } from "./types";
import { ResultFilter, ResultSortField, ResultSortOrder } from "@/types";
import { getWorkflowStep, getSessionStatus, isReadyToCompare, getMetrics } from "./selectors";

export function useWorkspace(type: "sales" | "purchases") {
  const router = useRouter();
  const { notify } = useToast();
  const [fromDate, setFromDate] = useState("");
  const [toDate, setToDate] = useState("");
  const [fileStatuses, setFileStatuses] = useState<KraFileTag[]>([]);
  // Filenames with a delete in flight, so their tag can show a spinner and refuse a
  // second click.
  const [removingFiles, setRemovingFiles] = useState<string[]>([]);
  // How far through a windowed SAP load we are, so the card can say "3 of 5" instead of
  // spinning silently for a minute.
  const [sapProgress, setSapProgress] = useState<{ done: number; total: number } | null>(null);
  
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

    // A long range is fetched as a series of shorter windows, each appending to the same
    // session, so the table fills as they land instead of staying empty until SAP has
    // returned everything. Short ranges stay a single request.
    const windows = splitDateRange(fromDate, toDate);
    setSapProgress({ done: 0, total: windows.length });

    // Rows held on screen. The first page of an append-only session stops changing once
    // it is full, so it is only re-read while still short of one.
    let held: Invoice[] = [];
    let activeSession: string | null = null;

    try {
      for (const [index, window] of windows.entries()) {
        const data = await fetchInvoicesPreview(
          type, window.from, window.to, activeSession ?? undefined
        );
        activeSession = data.session_id;
        setSessionId(data.session_id);

        const total = data.total_sap_records ?? data.count;

        if (held.length === 0) {
          // Nothing loaded yet, so this window's own rows are the session's first page.
          held = data.invoices;
          sapPagination.reset(held, total, Math.ceil(total / 100));
        } else if (held.length < Math.min(100, total)) {
          const firstPage = await fetchInvoicesPage(data.session_id, "SAP", 1, 100);
          held = firstPage.items;
          sapPagination.reset(firstPage.items, firstPage.total, firstPage.total_pages);
        } else {
          // Page one is settled; only the running total moves.
          sapPagination.reset(held, total, Math.ceil(total / 100));
        }

        setSapProgress({ done: index + 1, total: windows.length });
      }

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

      // A window that fails leaves the session holding only part of the range. Comparing
      // against that would report every unfetched invoice as missing from SAP, so the
      // load is failed outright rather than presented as a smaller result.
      sapPagination.reset();
      setSessionId(null);
      setUiState(prev => ({
        ...prev,
        sap: {
          status: AsyncStatus.Error,
          error: windows.length > 1
            ? `${errorMessage} (loading ${fromDate} to ${toDate}); nothing was kept — retry the load.`
            : errorMessage,
        },
      }));
    } finally {
      setSapProgress(null);
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

    // Every selected file gets a tag immediately, each resolving as its own upload
    // returns. Sending the whole selection as one request meant a user picking eight
    // section exports watched a single spinner with no idea which had gone in.
    const selected = files.map(f => f.name);
    setFileStatuses(prev => [
      ...prev.filter(p => !selected.includes(p.filename)),
      ...files.map(f => ({
        filename: f.name, rows: 0, parsed: 0, errors_count: 0, errors: [], pending: true,
      })),
    ]);

    let total = kraPagination.totalItems ?? 0;
    const failures: string[] = [];

    try {
      for (const file of files) {
        try {
          const data = await uploadInvoicesCSV(type, sessionId, [file]);
          const status = data.files.find(f => f.filename === file.name);
          setFileStatuses(prev =>
            prev.map(p => (p.filename === file.name ? { ...(status ?? p), pending: false } : p))
          );

          total = data.total_kra_records;

          // Re-read page 1 rather than seeding with the rows just uploaded: an append
          // leaves earlier sections ahead of these in the preview.
          const firstPage = await fetchInvoicesPage(sessionId, "KRA", 1, 100);
          kraPagination.reset(firstPage.items, firstPage.total, firstPage.total_pages);
        } catch (err: unknown) {
          // One bad file must not discard the ones that imported cleanly, so the tag is
          // marked failed and the remaining files still go up.
          const message = err instanceof Error ? err.message : "Upload failed";
          failures.push(file.name);
          setFileStatuses(prev =>
            prev.map(p =>
              p.filename === file.name
                ? { ...p, pending: false, errors_count: 1, errors: [{ row: 0, column: null, message }] }
                : p
            )
          );
        }
      }

      if (total > 0) {
        setUiState(prev => ({ ...prev, kra: { status: AsyncStatus.Loaded } }));
        if (failures.length) {
          notify(`${failures.length} of ${files.length} file(s) could not be imported`, "error");
        }
      } else {
        setUiState(prev => ({
          ...prev,
          kra: {
            status: AsyncStatus.Error,
            error: `None of the selected file${files.length !== 1 ? "s" : ""} could be imported.`,
          },
        }));
      }
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
    setSapProgress(null);
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
    sapProgress,
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
