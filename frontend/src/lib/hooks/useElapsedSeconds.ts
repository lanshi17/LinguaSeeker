
import { useEffect, useState } from "react";

/**
 * Returns the seconds elapsed since `start`. Updates every 250ms so live
 * "running" durations tick visibly without a re-render storm.
 */
export function useElapsedSeconds(start: string | null | undefined): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!start) return;
    const t = setInterval(() => setNow(Date.now()), 250);
    return () => clearInterval(t);
  }, [start]);
  if (!start) return 0;
  const ms = now - new Date(start).getTime();
  return Math.max(0, ms / 1000);
}
