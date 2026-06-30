import { useMemo, useCallback } from "react";

interface UsePaginationParams {
  page: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

export function usePagination({ page, totalPages, onPageChange }: UsePaginationParams) {
  const pageNumbers = useMemo(() => {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
    const pages: number[] = [1];
    const windowStart = Math.max(2, page - 1);
    const windowEnd = Math.min(totalPages - 1, page + 1);
    if (windowStart > 2) pages.push(-1);
    for (let p = windowStart; p <= windowEnd; p++) pages.push(p);
    if (windowEnd < totalPages - 1) pages.push(-2);
    pages.push(totalPages);
    return pages;
  }, [totalPages, page]);

  const canPrev = page > 1;
  const canNext = page < totalPages;
  const goPrev = useCallback(() => { if (canPrev) onPageChange(page - 1); }, [canPrev, page, onPageChange]);
  const goNext = useCallback(() => { if (canNext) onPageChange(page + 1); }, [canNext, page, onPageChange]);
  const goTo = useCallback((p: number) => { if (p >= 1 && p <= totalPages) onPageChange(p); }, [totalPages, onPageChange]);

  return { pageNumbers, canPrev, canNext, goPrev, goNext, goTo };
}
