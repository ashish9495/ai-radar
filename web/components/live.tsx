"use client";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { getPipelineStatus } from "@/lib/api";
import type { PipelineStatus } from "@/lib/types";

/** Polls the pipeline status every minute while the tab is visible. When new items have been
 * collected or processed, `tick` increments and every feed on the page refetches by itself. */
interface Live { status: PipelineStatus | null; tick: number; lastChecked: Date | null; newSince: number; refresh: () => void }
const Ctx = createContext<Live>({ status: null, tick: 0, lastChecked: null, newSince: 0, refresh: () => {} });
export const useLive = () => useContext(Ctx);

const POLL_MS = 60_000;
const signature = (s: PipelineStatus) => `${s.newest_discovery_at}|${s.last_process_success}|${s.discoveries_24h}`;

export function LiveProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [tick, setTick] = useState(0);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [newSince, setNewSince] = useState(0);
  const sig = useRef<string | null>(null);
  const base24h = useRef<number | null>(null);

  const check = useCallback(async () => {
    try {
      const s = await getPipelineStatus();
      setStatus(s);
      setLastChecked(new Date());
      const next = signature(s);
      if (base24h.current === null) base24h.current = s.discoveries_24h;
      if (sig.current !== null && sig.current !== next) {
        setTick((t) => t + 1);
        setNewSince(Math.max(0, s.discoveries_24h - (base24h.current ?? s.discoveries_24h)));
      }
      sig.current = next;
    } catch { /* keep last known status; the strip shows its age */ }
  }, []);

  useEffect(() => {
    void check();
    const id = setInterval(() => { if (document.visibilityState === "visible") void check(); }, POLL_MS);
    const onVis = () => { if (document.visibilityState === "visible") void check(); };
    document.addEventListener("visibilitychange", onVis);
    return () => { clearInterval(id); document.removeEventListener("visibilitychange", onVis); };
  }, [check]);

  const refresh = useCallback(() => { setTick((t) => t + 1); void check(); }, [check]);
  return <Ctx.Provider value={{ status, tick, lastChecked, newSince, refresh }}>{children}</Ctx.Provider>;
}
