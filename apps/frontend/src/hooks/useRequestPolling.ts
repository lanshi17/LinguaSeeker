import { useEffect, useRef, useState } from 'react';

import { ApiError } from '../services/http';

type PollState<T> = {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
};

type PollOptions = {
  enabled?: boolean;
  intervalMs?: number;
};

export function useRequestPolling<T>(fetcher: (signal: AbortSignal) => Promise<T>, options: PollOptions = {}) {
  const enabled = options.enabled ?? true;
  const intervalMs = options.intervalMs ?? 2000;

  const [state, setState] = useState<PollState<T>>({
    data: null,
    loading: enabled,
    error: null
  });

  const timerRef = useRef<number | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (!enabled) {
      setState((s) => ({ ...s, loading: false }));
      return;
    }

    let stopped = false;

    const tick = async () => {
      if (stopped) return;
      if (document.visibilityState === 'hidden') {
        timerRef.current = window.setTimeout(tick, intervalMs);
        return;
      }

      abortRef.current?.abort();
      const ac = new AbortController();
      abortRef.current = ac;

      try {
        setState((s) => ({ ...s, loading: true, error: null }));
        const data = await fetcher(ac.signal);
        if (stopped) return;
        setState({ data, loading: false, error: null });
      } catch (err) {
        if (stopped) return;
        if (err instanceof DOMException && err.name === 'AbortError') {
          return;
        }
        const apiErr = err instanceof ApiError ? err : new ApiError({ status: 0, message: 'Request failed', responseBody: err });
        setState((s) => ({ ...s, loading: false, error: apiErr }));
      } finally {
        if (!stopped) {
          timerRef.current = window.setTimeout(tick, intervalMs);
        }
      }
    };

    void tick();

    return () => {
      stopped = true;
      abortRef.current?.abort();
      if (timerRef.current !== null) {
        window.clearTimeout(timerRef.current);
      }
    };
  }, [enabled, fetcher, intervalMs]);

  return state;
}
