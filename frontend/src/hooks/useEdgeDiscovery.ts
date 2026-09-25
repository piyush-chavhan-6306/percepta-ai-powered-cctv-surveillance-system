/**
 * PERCEPTA — Edge Discovery Hook
 * ==============================
 *
 * Determines at runtime whether the browser can reach:
 *   (a) A local FastAPI edge at 127.0.0.1:8000   → LOCAL MODE
 *   (b) A configured remote edge URL             → ONLINE MODE (hybrid)
 *   (c) No reachable backend                      → DEMO/OFFLINE MODE
 *
 * Resolution order:
 *   1. localStorage["percepta_backend_url"]   (operator-configured override)
 *   2. import.meta.env.VITE_API_URL          (build-time / Vercel env var)
 *   3. http://127.0.0.1:8000                  (localhost probe)
 *   4. OFFLINE (no backend reachable)
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "../api/client";

export type EdgeMode =
  | "probing"        // initial probe in progress
  | "local"          // local 127.0.0.1 FastAPI reachable
  | "online"         // remote tunnel / configured URL reachable
  | "offline";       // no backend reachable — demo data only

export interface EdgeState {
  mode: EdgeMode;
  backendUrl: string | null;
  latencyMs: number | null;
  lastChecked: Date | null;
  error: string | null;
  /** Re-probe immediately */
  refresh: () => void;
  /** Operator manually sets a remote edge URL */
  setEdgeUrl: (url: string) => void;
  /** Clear the configured edge URL (fall back to local / offline) */
  clearEdgeUrl: () => void;
}

const LOCAL_CANDIDATES = [
  "http://127.0.0.1:8000",
  "http://localhost:8000",
];

const STORAGE_KEY = "percepta_backend_url";
const PROBE_INTERVAL_MS = 30_000; // re-probe every 30 s

async function probeUrl(url: string, timeoutMs = 4000): Promise<{ ok: boolean; latency: number }> {
  const start = performance.now();
  try {
    const ctrl = new AbortController();
    const timer = setTimeout(() => ctrl.abort(), timeoutMs);
    const res = await fetch(`${url.replace(/\/+$/, "")}/api/health`, {
      signal: ctrl.signal,
      cache: "no-store",
    });
    clearTimeout(timer);
    const latency = Math.round(performance.now() - start);
    return { ok: res.ok, latency };
  } catch {
    return { ok: false, latency: -1 };
  }
}

export function useEdgeDiscovery(): EdgeState {
  const [mode, setMode] = useState<EdgeMode>("probing");
  const [backendUrl, setBackendUrlState] = useState<string | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [lastChecked, setLastChecked] = useState<Date | null>(null);
  const [error, setError] = useState<string | null>(null);
  const probeRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const doProbe = useCallback(async () => {
    setMode("probing");
    setError(null);

    // 1. Operator-configured URL from localStorage
    const stored = typeof window !== "undefined"
      ? (localStorage.getItem(STORAGE_KEY) || "").trim()
      : "";

    // 2. VITE build-time URL
    const viteUrl = (import.meta.env.VITE_API_URL || "").trim().replace(/\/+$/, "");

    // Build probe list (configured URL first, then local fallback)
    const candidates: string[] = [];
    if (stored) candidates.push(stored);
    if (viteUrl && !candidates.includes(viteUrl)) candidates.push(viteUrl);
    if (!window.location.hostname.match(/vercel\.app|ngrok/)) {
      candidates.push(...LOCAL_CANDIDATES);
    }

    for (const candidate of candidates) {
      const { ok, latency } = await probeUrl(candidate);
      if (ok) {
        const isLocal = LOCAL_CANDIDATES.some(l => candidate.startsWith(l.replace(/\/+$/, "")));
        const resolvedMode: EdgeMode = isLocal ? "local" : "online";

        setBackendUrlState(candidate);
        setLatencyMs(latency);
        setMode(resolvedMode);
        setLastChecked(new Date());

        // Keep api in sync
        api.setBaseUrl(candidate);
        return;
      }
    }

    // Nothing reachable
    setMode("offline");
    setBackendUrlState(null);
    setLatencyMs(null);
    setLastChecked(new Date());
    setError("No PERCEPTA edge node reachable. Running in DEMO mode.");
  }, []);

  // Initial probe + recurring re-probe
  useEffect(() => {
    doProbe();
    probeRef.current = setInterval(doProbe, PROBE_INTERVAL_MS);
    return () => {
      if (probeRef.current) clearInterval(probeRef.current);
    };
  }, [doProbe]);

  const refresh = useCallback(() => {
    if (probeRef.current) clearInterval(probeRef.current);
    doProbe().then(() => {
      probeRef.current = setInterval(doProbe, PROBE_INTERVAL_MS);
    });
  }, [doProbe]);

  const setEdgeUrl = useCallback(
    (url: string) => {
      const cleaned = url.trim().replace(/\/+$/, "");
      if (typeof window !== "undefined") {
        localStorage.setItem(STORAGE_KEY, cleaned);
      }
      api.setBaseUrl(cleaned);
      refresh();
    },
    [refresh],
  );

  const clearEdgeUrl = useCallback(() => {
    if (typeof window !== "undefined") {
      localStorage.removeItem(STORAGE_KEY);
    }
    refresh();
  }, [refresh]);

  return {
    mode,
    backendUrl,
    latencyMs,
    lastChecked,
    error,
    refresh,
    setEdgeUrl,
    clearEdgeUrl,
  };
}
