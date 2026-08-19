import { useState, useCallback, useEffect, useRef } from "react";
import { PaginatedResponse } from "@/types";

interface UsePaginationOptions {
  limit?: number;
  enabled?: boolean;
}

export function usePagination<T>(
  fetchPage: (page: number, limit: number) => Promise<PaginatedResponse<T>>,
  options: UsePaginationOptions = {}
) {
  const { limit = 100, enabled = false } = options;

  const [items, setItems] = useState<T[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  
  const [isInitialLoading, setIsInitialLoading] = useState(false);
  const [isLoadingMore, setIsLoadingMore] = useState(false);

  // Every request carries a ticket; only the newest one may write to state. Without
  // this, switching filter or sort quickly lets a slow earlier response land last and
  // leave the table showing rows that no longer match what is selected.
  const requestTicket = useRef(0);
  const nextTicket = () => (requestTicket.current += 1);
  const isCurrent = (ticket: number) => requestTicket.current === ticket;

  const hasMore = page < totalPages && items.length < total;

  const loadNextPage = useCallback(async () => {
    if (isInitialLoading || isLoadingMore || !hasMore) return;

    const ticket = nextTicket();
    setIsLoadingMore(true);
    try {
      const nextPage = page + 1;
      const res = await fetchPage(nextPage, limit);
      if (!isCurrent(ticket)) return;
      setItems((prev) => [...prev, ...res.items]);
      setPage(res.page);
      setTotal(res.total);
      setTotalPages(res.total_pages);
    } catch (err) {
      if (isCurrent(ticket)) console.error("Failed to load next page:", err);
    } finally {
      if (isCurrent(ticket)) setIsLoadingMore(false);
    }
  }, [page, isInitialLoading, isLoadingMore, hasMore, fetchPage, limit]);

  const reset = useCallback((initialItems: T[] = [], initialTotal = 0, initialTotalPages = 0) => {
    // Invalidate anything in flight, so a response from the previous session or filter
    // cannot append itself onto the fresh list.
    nextTicket();
    setItems(initialItems);
    setPage(1);
    setTotal(initialTotal);
    setTotalPages(initialTotalPages);
    setIsInitialLoading(false);
    setIsLoadingMore(false);
  }, []);

  useEffect(() => {
    if (enabled) {
      const ticket = nextTicket();
      const fetchInitial = async () => {
        setIsInitialLoading(true);
        // A fresh load supersedes any append in flight, whose own `finally` will now
        // decline to clear this flag.
        setIsLoadingMore(false);
        try {
          const res = await fetchPage(1, limit);
          if (!isCurrent(ticket)) return;
          setItems(res.items);
          setPage(res.page);
          setTotal(res.total);
          setTotalPages(res.total_pages);
        } catch (err) {
          if (isCurrent(ticket)) console.error("Failed to load initial page:", err);
        } finally {
          if (isCurrent(ticket)) setIsInitialLoading(false);
        }
      };
      fetchInitial();
    }
  }, [enabled, fetchPage, limit]);

  return {
    items,
    setItems,
    page,
    total,
    totalItems: total,
    totalPages,
    isInitialLoading,
    isLoadingMore,
    hasMore,
    loadNextPage,
    reset,
  };
}
