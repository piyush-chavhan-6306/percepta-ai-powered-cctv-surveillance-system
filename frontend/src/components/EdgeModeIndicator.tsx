/**
 * PERCEPTA — Edge Mode Indicator + Setup Modal
 * ==============================================
 *
 * Displays the current operational mode (LOCAL / ONLINE / OFFLINE / PROBING)
 * in the dashboard header and provides an operator interface to configure the
 * remote edge URL (ngrok tunnel or any HTTPS endpoint hosting the FastAPI edge).
 */

import React, { useState, useContext, createContext, useCallback, useEffect } from "react";
import {
  Server,
  Wifi,
  WifiOff,
  Loader2,
  X,
  Link2,
  CheckCircle2,
  AlertTriangle,
  Info,
  Globe,
  HardDrive,
  Copy,
  Check,
} from "lucide-react";
import { useEdgeDiscovery, EdgeMode } from "../hooks/useEdgeDiscovery";

// ─── Context ──────────────────────────────────────────────────────────────────
interface EdgeContext {
  mode: EdgeMode;
  backendUrl: string | null;
  latencyMs: number | null;
  refresh: () => void;
  setEdgeUrl: (url: string) => void;
  clearEdgeUrl: () => void;
  openSetup: () => void;
}

const EdgeCtx = createContext<EdgeContext | null>(null);

export function useEdgeContext(): EdgeContext {
  const ctx = useContext(EdgeCtx);
  if (!ctx) throw new Error("useEdgeContext must be used inside EdgeProvider");
  return ctx;
}

// ─── Provider ─────────────────────────────────────────────────────────────────
export function EdgeProvider({ children }: { children: React.ReactNode }) {
  const edge = useEdgeDiscovery();
  const [setupOpen, setSetupOpen] = useState(false);

  return (
    <EdgeCtx.Provider
      value={{
        ...edge,
        openSetup: () => setSetupOpen(true),
      }}
    >
      {children}
      {setupOpen && <EdgeSetupModal onClose={() => setSetupOpen(false)} />}
    </EdgeCtx.Provider>
  );
}

// ─── Mode colour / label config ───────────────────────────────────────────────
interface ModeConfig {
  label: string;
  Icon: React.ElementType;
  dot: string;
  bg: string;
  border: string;
  text: string;
  pulse: boolean;
}

function getModeConfig(mode: EdgeMode): ModeConfig {
  switch (mode) {
    case "probing":
      return {
        label: "PROBING",
        Icon: Loader2,
        dot: "#6b7280",
        bg: "bg-[#6b7280]/10",
        border: "border-[#6b7280]/30",
        text: "text-[#9ca3af]",
        pulse: false,
      };
    case "local":
      return {
        label: "LOCAL EDGE",
        Icon: HardDrive,
        dot: "#33f0b4",
        bg: "bg-[#33f0b4]/10",
        border: "border-[#33f0b4]/30",
        text: "text-[#33f0b4]",
        pulse: true,
      };
    case "online":
      return {
        label: "ONLINE",
        Icon: Globe,
        dot: "#3b82f6",
        bg: "bg-[#3b82f6]/10",
        border: "border-[#3b82f6]/30",
        text: "text-[#60a5fa]",
        pulse: true,
      };
    case "offline":
      return {
        label: "OFFLINE",
        Icon: WifiOff,
        dot: "#ef4444",
        bg: "bg-[#ef4444]/10",
        border: "border-[#ef4444]/30",
        text: "text-[#f87171]",
        pulse: false,
      };
  }
}

// ─── Compact badge for dashboard header ───────────────────────────────────────
export function EdgeModeBadge() {
  const { mode, latencyMs, openSetup } = useEdgeContext();
  const cfg = getModeConfig(mode);

  return (
    <button
      type="button"
      onClick={openSetup}
      title={`Edge Mode: ${cfg.label} — click to configure`}
      className={`flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono font-bold tracking-wider uppercase border transition-all cursor-pointer hover:opacity-80 ${cfg.bg} ${cfg.border} ${cfg.text}`}
    >
      {mode === "probing" ? (
        <cfg.Icon size={10} className="animate-spin" />
      ) : (
        <>
          <span
            className={`w-1.5 h-1.5 rounded-full ${cfg.pulse ? "animate-pulse" : ""}`}
            style={{ backgroundColor: cfg.dot }}
          />
          <cfg.Icon size={10} />
        </>
      )}
      <span>{cfg.label}</span>
      {latencyMs !== null && latencyMs >= 0 && (
        <span className="opacity-60 ml-0.5">{latencyMs}ms</span>
      )}
    </button>
  );
}

// ─── Setup Modal ───────────────────────────────────────────────────────────────
function EdgeSetupModal({ onClose }: { onClose: () => void }) {
  const { mode, backendUrl, latencyMs, refresh, setEdgeUrl, clearEdgeUrl } = useEdgeContext();
  const [inputUrl, setInputUrl] = useState(backendUrl || "");
  const [probing, setProbing] = useState(false);
  const [probeResult, setProbeResult] = useState<{ ok: boolean; ms: number } | null>(null);
  const [copied, setCopied] = useState(false);

  const cfg = getModeConfig(mode);

  const handleProbe = useCallback(async () => {
    const url = inputUrl.trim().replace(/\/+$/, "");
    if (!url) return;
    setProbing(true);
    setProbeResult(null);
    const start = performance.now();
    try {
      const ctrl = new AbortController();
      setTimeout(() => ctrl.abort(), 5000);
      const res = await fetch(`${url}/api/health`, { signal: ctrl.signal, cache: "no-store" });
      const ms = Math.round(performance.now() - start);
      setProbeResult({ ok: res.ok, ms });
    } catch {
      setProbeResult({ ok: false, ms: -1 });
    } finally {
      setProbing(false);
    }
  }, [inputUrl]);

  const handleApply = useCallback(() => {
    const url = inputUrl.trim().replace(/\/+$/, "");
    if (url) {
      setEdgeUrl(url);
    } else {
      clearEdgeUrl();
    }
    onClose();
  }, [inputUrl, setEdgeUrl, clearEdgeUrl, onClose]);

  const handleCopyCmd = useCallback(() => {
    const url = backendUrl || "";
    const cmd = `localStorage.setItem('percepta_backend_url', '${url}')`;
    navigator.clipboard?.writeText(cmd);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [backendUrl]);

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/70 backdrop-blur-sm">
      <div className="w-[480px] max-w-[96vw] bg-[#07090c] border border-[#1b2530] rounded-2xl shadow-2xl overflow-hidden font-sans">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-[#1b2530] bg-[#090d13]">
          <div className="flex items-center gap-3">
            <Server size={18} className="text-[#33f0b4]" />
            <span className="font-['Chakra_Petch',sans-serif] font-bold text-white text-sm tracking-wider uppercase">
              Edge Node Configuration
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-[#4a5568] hover:text-white transition-colors cursor-pointer"
          >
            <X size={18} />
          </button>
        </div>

        {/* Current status */}
        <div className="px-5 pt-4">
          <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border ${cfg.bg} ${cfg.border}`}>
            <cfg.Icon
              size={20}
              className={`${cfg.text} ${mode === "probing" ? "animate-spin" : ""}`}
            />
            <div className="flex-1 min-w-0">
              <div className={`text-xs font-mono font-bold tracking-wider uppercase ${cfg.text}`}>
                {cfg.label}
              </div>
              <div className="text-[11px] text-[#8b9bb0] font-mono mt-0.5 truncate">
                {backendUrl || "No backend reachable"}
                {latencyMs !== null && latencyMs >= 0 && ` · ${latencyMs}ms`}
              </div>
            </div>
            <button
              type="button"
              onClick={refresh}
              className="text-[#4a5568] hover:text-[#33f0b4] transition-colors cursor-pointer"
              title="Re-probe"
            >
              <Loader2 size={14} />
            </button>
          </div>
        </div>

        {/* Architecture explanation */}
        <div className="px-5 pt-4">
          <div className="flex items-start gap-2 text-[11px] text-[#8b9bb0] font-mono bg-[#0c1015] border border-[#1b2530] rounded-lg px-3 py-3">
            <Info size={13} className="mt-0.5 text-[#60a5fa] shrink-0" />
            <div>
              <span className="text-[#cbd5e1] font-semibold">How it works: </span>
              The local PERCEPTA edge runs YOLO on your machine. Start it with{" "}
              <span className="text-[#33f0b4]">python start_edge.py --tunnel</span> to get a
              public ngrok URL. Paste that URL below so this Vercel C2 can reach live
              YOLO inference.
            </div>
          </div>
        </div>

        {/* URL input */}
        <div className="px-5 pt-4">
          <label className="block text-[11px] font-mono font-semibold text-[#8b9bb0] uppercase tracking-wider mb-2">
            <Link2 size={11} className="inline mr-1.5" />
            Edge Node URL
          </label>
          <div className="flex gap-2">
            <input
              type="url"
              value={inputUrl}
              onChange={(e) => {
                setInputUrl(e.target.value);
                setProbeResult(null);
              }}
              placeholder="https://xxxxx.ngrok-free.app  or  http://127.0.0.1:8000"
              className="flex-1 bg-[#0c1015] border border-[#1b2530] rounded-lg px-3 py-2.5 text-[12px] font-mono text-[#cbd5e1] placeholder-[#3a4555] focus:outline-none focus:border-[#33f0b4]/50 focus:ring-1 focus:ring-[#33f0b4]/20 transition-colors"
            />
            <button
              type="button"
              onClick={handleProbe}
              disabled={probing || !inputUrl.trim()}
              className="px-3 py-2 bg-[#0f1823] hover:bg-[#162030] border border-[#263340] text-[#60a5fa] rounded-lg text-[11px] font-mono font-semibold transition-colors disabled:opacity-40 cursor-pointer"
            >
              {probing ? <Loader2 size={13} className="animate-spin" /> : "TEST"}
            </button>
          </div>

          {probeResult && (
            <div
              className={`mt-2 flex items-center gap-2 text-[11px] font-mono px-3 py-2 rounded-lg border ${
                probeResult.ok
                  ? "bg-[#33f0b4]/8 border-[#33f0b4]/20 text-[#33f0b4]"
                  : "bg-[#ef4444]/8 border-[#ef4444]/20 text-[#f87171]"
              }`}
            >
              {probeResult.ok ? (
                <>
                  <CheckCircle2 size={12} />
                  <span>
                    Reachable — {probeResult.ms}ms. Click APPLY to use this endpoint.
                  </span>
                </>
              ) : (
                <>
                  <AlertTriangle size={12} />
                  <span>
                    Not reachable. Check the URL and ensure the edge node is running.
                  </span>
                </>
              )}
            </div>
          )}
        </div>

        {/* Start edge instructions */}
        <div className="px-5 pt-4">
          <div className="text-[11px] font-mono text-[#4a5568] mb-1.5 uppercase tracking-wider">
            Quick start
          </div>
          <div className="bg-[#0a0d11] border border-[#1a2030] rounded-lg px-4 py-3 space-y-1.5">
            {[
              "# 1. Activate virtualenv",
              "venv\\Scripts\\activate.bat",
              "",
              "# 2. Start edge with public tunnel",
              "python start_edge.py --tunnel",
              "",
              "# 3. Copy the printed ngrok URL here",
            ].map((line, i) => (
              <div
                key={i}
                className={`text-[11px] font-mono ${
                  line.startsWith("#") ? "text-[#3d5068]" : line ? "text-[#a3e635]" : ""
                }`}
              >
                {line || "\u00a0"}
              </div>
            ))}
          </div>
        </div>

        {/* Copy browser command */}
        {backendUrl && (
          <div className="px-5 pt-3">
            <div className="flex items-center justify-between text-[11px] text-[#4a5568] font-mono mb-1">
              <span className="uppercase tracking-wider">Browser console override</span>
              <button
                type="button"
                onClick={handleCopyCmd}
                className="flex items-center gap-1 text-[#60a5fa] hover:text-[#93c5fd] transition-colors cursor-pointer"
              >
                {copied ? <Check size={11} /> : <Copy size={11} />}
                {copied ? "Copied" : "Copy"}
              </button>
            </div>
            <div className="bg-[#0a0d11] border border-[#1a2030] rounded-lg px-3 py-2 text-[10px] font-mono text-[#60a5fa] truncate">
              localStorage.setItem('percepta_backend_url', '{backendUrl}')
            </div>
          </div>
        )}

        {/* Actions */}
        <div className="flex items-center justify-between px-5 pt-4 pb-5 mt-2">
          <button
            type="button"
            onClick={clearEdgeUrl}
            className="text-[11px] font-mono text-[#4a5568] hover:text-[#f87171] transition-colors cursor-pointer"
          >
            Clear & reset
          </button>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-[12px] font-mono text-[#8b9bb0] hover:text-white border border-[#1b2530] rounded-lg transition-colors cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleApply}
              className="px-5 py-2 bg-[#33f0b4] hover:bg-[#28dfa3] text-black font-bold text-[12px] font-mono rounded-lg transition-colors cursor-pointer shadow-[0_0_14px_rgba(51,240,180,0.3)]"
            >
              APPLY
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
