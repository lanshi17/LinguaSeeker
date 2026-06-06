"use client";

import { useState, useEffect } from "react";

/**
 * Debounce a value by the given delay (ms).
 *
 * Usage: const debouncedQuery = useDebounce(searchQuery, 300);
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);

  return debounced;
}
