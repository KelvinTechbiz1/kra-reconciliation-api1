import React, { useEffect, useRef } from "react";
import { Loader2 } from "lucide-react";
import { AsyncState, AsyncStatus } from "@/features/sales/workspace/types";

export interface Column<T> {
  key: string;
  header: React.ReactNode;
  accessor: (item: T) => React.ReactNode;
  className?: string;
  skeletonWidth?: string; // e.g. "w-20", "w-32"
}

interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  asyncState: AsyncState;
  emptyState: React.ReactNode;
  errorState: React.ReactNode;
  className?: string;
  hasMore?: boolean;
  isLoadingMore?: boolean;
  onLoadMore?: () => void;
  /** Shown in the footer row while more data is still being fetched into the table. */
  loadingMoreLabel?: string;
}

export function DataTable<T>({ 
  data, 
  columns, 
  asyncState, 
  emptyState, 
  errorState,
  className = "",
  hasMore = false,
  isLoadingMore = false,
  onLoadMore,
  loadingMoreLabel = "Loading more records...",
}: DataTableProps<T>) {
  const containerRef = useRef<HTMLDivElement>(null);
  const sentinelRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!onLoadMore || !hasMore || isLoadingMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0].isIntersecting) {
          onLoadMore();
        }
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
  
  // Rows already fetched stay on screen while more are still arriving. Skeletons are
  // only honest before anything has landed; once the table holds data, replacing it with
  // placeholders hides work that is already done.
  const isStreaming = asyncState.status === AsyncStatus.Loading && data.length > 0;
  const showRows = asyncState.status === AsyncStatus.Loaded || isStreaming;

  return (
    <div className={`flex flex-col relative w-full h-full ${className}`}>
      <div ref={containerRef} onScroll={handleScroll} className="overflow-auto flex-1 relative">
        <table className="w-full text-sm text-left whitespace-nowrap relative">
          <thead className="bg-slate-50 text-slate-500 uppercase text-xs tracking-wider border-b border-slate-200 sticky top-0 z-10 shadow-[0_1px_0_0_rgba(226,232,240,1)]">
            <tr>
              {columns.map(col => (
                <th key={col.key} className={`px-4 py-3 font-medium bg-slate-50 ${col.className || ""}`}>
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {asyncState.status === AsyncStatus.Loading && data.length === 0 && (
              <>
                {[...Array(5)].map((_, i) => (
                  <tr key={`skeleton-${i}`} className="animate-pulse transition-opacity duration-200">
                    {columns.map(col => (
                      <td key={`sk-${col.key}`} className={`px-4 py-3 ${col.className || ""}`}>
                        <div className={`h-4 bg-slate-100 rounded ${col.skeletonWidth || "w-full"}`}></div>
                      </td>
                    ))}
                  </tr>
                ))}
              </>
            )}

            {showRows && data.length > 0 && (
              <>
                {data.map((row, idx) => (
                  <tr key={idx} className="hover:bg-slate-50 transition-colors animate-fade-in">
                    {columns.map(col => (
                      <td key={col.key} className={`px-4 py-2 text-slate-700 ${col.className || ""}`}>
                        {col.accessor(row)}
                      </td>
                    ))}
                  </tr>
                ))}

                {(isLoadingMore || isStreaming) && (
                  <tr key="loading-more-indicator">
                    <td colSpan={columns.length} className="py-3 text-center text-xs text-slate-500 bg-slate-50/60">
                      <div className="inline-flex items-center justify-center gap-2 font-medium">
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-[#0e1734]" />
                        {isStreaming ? loadingMoreLabel : "Loading more records..."}
                      </div>
                    </td>
                  </tr>
                )}
              </>
            )}
          </tbody>
        </table>

        {hasMore && <div ref={sentinelRef} className="h-4 w-full" />}

        {/* Full-panel overlays for Idle, Error, or Empty Loaded states */}
        {asyncState.status === AsyncStatus.Idle && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/80 animate-fade-in mt-10">
            {emptyState}
          </div>
        )}

        {asyncState.status === AsyncStatus.Error && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/80 animate-fade-in mt-10">
            {errorState}
          </div>
        )}

        {asyncState.status === AsyncStatus.Loaded && data.length === 0 && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/80 animate-fade-in mt-10">
            <div className="text-center text-slate-500">
              No records found.
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
