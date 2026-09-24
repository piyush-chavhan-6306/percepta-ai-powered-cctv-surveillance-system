import React, { useState } from "react";
import {
  AlertTriangle,
  Shield,
  Clock,
  RefreshCw,
  Check,
  ChevronRight,
  PlayCircle,
  Camera,
  Trash2,
} from "lucide-react";
import { useSurveillance } from "../store/surveillanceContext";
import type { AlertItem } from "../types/surveillance";

interface TacticalThreatFeedProps {
  onInspectAlert?: (alert: any) => void;
  onReplayEvent?: (alert?: any) => void;
  onSeekTime?: (timestamp: string | number, cameraId?: string) => void;
}

export const TacticalThreatFeed: React.FC<TacticalThreatFeedProps> = ({
  onInspectAlert,
  onReplayEvent,
  onSeekTime,
}) => {
  const { alerts, acknowledgeAlert, refreshAlerts, clearAllAlerts } = useSurveillance();
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isClearing, setIsClearing] = useState(false);

  const handleClear = async () => {
    setIsClearing(true);
    try {
      await clearAllAlerts();
    } catch (err) {
      console.error("Failed to clear alerts:", err);
    } finally {
      setIsClearing(false);
    }
  };

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await refreshAlerts();
    } finally {
      setTimeout(() => setIsRefreshing(false), 500);
    }
  };

  const handleAcknowledge = async (e: React.MouseEvent, alertId: string) => {
    e.stopPropagation();
    try {
      await acknowledgeAlert(alertId);
    } catch (err) {
      console.error("Failed to acknowledge alert:", err);
    }
  };

  const formatTime = (ts: string | number) => {
    try {
      const d = new Date(ts);
      if (isNaN(d.getTime())) return String(ts);
      return d.toLocaleTimeString("en-US", {
        hour12: false,
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch {
      return String(ts);
    }
  };

  // Filter alerts by selected severity
  const filteredAlerts = alerts.filter((a) => {
    if (filterSeverity === "ALL") return true;
    const sev = String(a.severity || "NORMAL").toUpperCase();
    if (filterSeverity === "CRITICAL") return sev === "CRITICAL";
    if (filterSeverity === "RESTRICTED") return sev === "RESTRICTED" || sev === "WARNING";
    if (filterSeverity === "RESOLVED") return a.is_acknowledged;
    return true;
  });

  const activeCount = alerts.filter((a) => !a.is_acknowledged).length;

  return (
    <div
      className="w-full h-full flex flex-col bg-[#0c1015] border border-[#1b2530] rounded-xl overflow-hidden font-sans select-none"
      data-purpose="tactical-incident-feed"
    >
      {/* ── Header ── */}
      <div className="px-3.5 py-2.5 border-b border-[#1b2530] bg-[#090d12] flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <div className="w-5 h-5 rounded flex items-center justify-center bg-[#ff4757]/15 text-[#ff4757] border border-[#ff4757]/40 shrink-0">
            <AlertTriangle size={12} />
          </div>
          <span className="font-['Chakra_Petch',sans-serif] font-bold text-white text-[13.5px] tracking-wider uppercase">
            TACTICAL INCIDENT FEED
          </span>
          <span className="flex items-center gap-1 px-1.5 py-0.5 rounded-full bg-[#ff4757]/15 text-[#ff4757] border border-[#ff4757]/35 font-mono text-[8.5px] font-bold shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-[#ff4757] animate-pulse" />
            {activeCount > 0 ? `${activeCount} ACTIVE` : "ACTIVE"}
          </span>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="bg-[#070a0f] border border-[#1b2530] rounded text-[#cbd5e1] font-mono text-[10px] px-2.5 py-1 focus:outline-none cursor-pointer"
          >
            <option value="ALL">ALL SEVERITY</option>
            <option value="CRITICAL">CRITICAL ONLY</option>
            <option value="RESTRICTED">RESTRICTED</option>
            <option value="RESOLVED">RESOLVED</option>
          </select>
          <button
            type="button"
            onClick={handleRefresh}
            className="p-1 rounded text-[#869099] hover:text-white transition-colors cursor-pointer"
            title="Refresh Incidents"
          >
            <RefreshCw
              size={12}
              className={isRefreshing ? "animate-spin text-[#33f0b4]" : ""}
            />
          </button>
          <button
            type="button"
            onClick={handleClear}
            disabled={alerts.length === 0 || isClearing}
            className="px-2 py-0.5 rounded bg-[#ff4757]/15 hover:bg-[#ff4757]/25 text-[#ff4757] border border-[#ff4757]/30 text-[9px] font-mono flex items-center gap-1 transition-colors disabled:opacity-30 disabled:pointer-events-none cursor-pointer"
            title="Purge all logged incidents from system"
          >
            <Trash2 size={10} className={isClearing ? "animate-spin" : ""} />
            <span>CLEAR</span>
          </button>
        </div>
      </div>

      {/* ── Main Feed Body ── */}
      <div
        className="flex-1 min-h-0 overflow-y-auto p-2 space-y-2"
        style={{
          scrollbarWidth: "thin",
          scrollbarColor: "rgba(255,255,255,0.15) transparent",
        }}
      >
        {filteredAlerts.length === 0 ? (
          /* ── Purposeful Tactical Monitoring Empty State (Stage 3 Requirement) ── */
          <div className="h-full min-h-[300px] flex flex-col justify-between py-6 px-4 font-mono">
            {/* Sector Header */}
            <div className="text-center pb-2 border-b border-[#1b2530]/50">
              <span className="text-[9px] tracking-widest text-[#6c7d93] uppercase">
                SECTOR 07 // SURVEILLANCE MESH
              </span>
            </div>

            {/* Central Purposeful Monitoring State */}
            <div className="flex flex-col items-center justify-center text-center my-auto py-4">
              <div className="w-12 h-12 rounded-full border border-[#1b2530] bg-[#070a0f] flex items-center justify-center mb-3 text-[#33f0b4] shadow-[0_0_12px_rgba(51,240,180,0.15)]">
                <Shield size={22} strokeWidth={1.8} />
              </div>

              <p className="font-['Chakra_Petch',sans-serif] text-[13px] font-bold tracking-wider text-white uppercase leading-snug">
                NO ACTIVE INCIDENTS<br />IN SECTOR
              </p>

              <div className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#33f0b4]/10 border border-[#33f0b4]/30 text-[#33f0b4] text-[10px] mt-2 font-semibold">
                <span className="w-1.5 h-1.5 rounded-full bg-[#33f0b4] animate-pulse" />
                <span>Perimeter status normal</span>
              </div>
            </div>

            {/* System Monitoring Bottom Summary Box */}
            <div className="p-2.5 rounded-lg bg-[#070a0f] border border-[#1b2530] text-[9.5px] space-y-1">
              <div className="flex items-center justify-between text-[#869099]">
                <span>SYSTEM MONITORING</span>
                <span className="text-[#33f0b4] font-bold">ONLINE</span>
              </div>
              <div className="flex items-center justify-between text-[#64748b]">
                <span>CAMERAS ONLINE</span>
                <span className="text-white font-semibold">ACTIVE MESH</span>
              </div>
              <div className="flex items-center justify-between text-[#64748b]">
                <span>THREATS DETECTED</span>
                <span className="text-[#33f0b4] font-bold">0</span>
              </div>
            </div>
          </div>
        ) : (
          /* ── Populated Incident Cards ── */
          filteredAlerts.map((alert, idx) => {
            const sev = String(alert.severity || "NORMAL").toUpperCase();
            const isCrit = sev === "CRITICAL";
            const isRestricted = sev === "RESTRICTED" || sev === "WARNING";
            const threatScore =
              alert.threat_score ?? (isCrit ? 80 : isRestricted ? 55 : 20);

            return (
              <article
                key={alert.event_id || alert.alert_id || alert.seq_id || `alert-${idx}`}
                onClick={() => onInspectAlert?.(alert)}
                className={`p-2.5 rounded-lg border transition-all cursor-pointer relative group ${
                  alert.is_acknowledged
                    ? "bg-[#090d12]/60 border-[#1b2530]/60 opacity-65 hover:opacity-90"
                    : isCrit
                    ? "bg-[#0f1218] border-[#ff4757]/40 border-l-3 border-l-[#ff4757] hover:border-[#ff4757]/80"
                    : "bg-[#0c1016] border-[#f59e0b]/40 border-l-3 border-l-[#f59e0b] hover:border-[#f59e0b]/80"
                }`}
              >
                {/* Header Row: Severity, Threat Score, Camera, Time */}
                <div className="flex items-center justify-between font-mono text-[8.5px] pb-1.5 gap-1.5 flex-wrap">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span
                      className={`px-1.5 py-0.2 rounded font-bold uppercase ${
                        isCrit
                          ? "bg-[#ff4757]/20 text-[#ff4757]"
                          : isRestricted
                          ? "bg-[#f59e0b]/20 text-[#f59e0b]"
                          : "bg-[#33f0b4]/20 text-[#33f0b4]"
                      }`}
                    >
                      {sev}
                    </span>

                    <span
                      className={`px-1.5 py-0.2 rounded font-semibold ${
                        threatScore >= 70
                          ? "bg-[#ff4757]/15 text-[#ff8a80] border border-[#ff4757]/30"
                          : "bg-[#f59e0b]/15 text-[#f59e0b] border border-[#f59e0b]/30"
                      }`}
                    >
                      THREAT {threatScore}/100
                    </span>

                    <span className="text-[#33f0b4] flex items-center gap-0.5">
                      <Camera size={10} />
                      {alert.camera_id}
                    </span>

                    {alert.track_id && (
                      <span className="text-[#869099]">
                        #{alert.track_id}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-1 text-[#869099]">
                    <Clock size={10} />
                    <span>{formatTime(alert.timestamp)}</span>
                  </div>
                </div>

                {/* Evidence Thumbnail & Metadata Row */}
                <div className="flex items-start gap-2 mt-1">
                  {/* Evidence snapshot thumbnail (if available) */}
                  {(alert.evidence_snapshot_uri || alert.evidenceSnapshotUri) && (
                    <div className="shrink-0 w-14 h-10 rounded border border-[#1b2530] overflow-hidden bg-[#070a0f] relative">
                      <img
                        src={alert.evidence_snapshot_uri || alert.evidenceSnapshotUri}
                        alt="Evidence"
                        className="w-full h-full object-cover"
                        onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                      />
                      <span className="absolute bottom-0 left-0 right-0 bg-black/70 text-[6.5px] text-center text-[#33f0b4] font-mono py-px">
                        EVIDENCE
                      </span>
                    </div>
                  )}

                  <div className="flex-1 min-w-0">
                    {/* Message Body */}
                    <p className="text-[10.5px] text-[#e8ebe6] font-sans font-medium leading-snug line-clamp-2">
                      {alert.message || alert.reason || "Perimeter anomaly detected"}
                    </p>

                    {/* Inline Metadata Badges: ANPR plate, object class, confidence */}
                    <div className="flex items-center gap-1.5 mt-1 flex-wrap">
                      {(alert.object_class || alert.targetType) && (
                        <span className="px-1.5 py-0.2 rounded bg-[#1b2530] text-[#cbd5e1] font-mono text-[7.5px] font-bold uppercase">
                          {alert.object_class || alert.targetType}
                        </span>
                      )}
                      {(alert.plate_number || alert.plateNumber) && (
                        <span className="px-1.5 py-0.2 rounded bg-[#33f0b4]/15 text-[#33f0b4] font-mono text-[7.5px] font-bold border border-[#33f0b4]/30">
                          🚗 {alert.plate_number || alert.plateNumber}
                        </span>
                      )}
                      {alert.confidence && (
                        <span className="text-[7.5px] font-mono text-[#869099]">
                          {Math.round(Number(alert.confidence) * 100)}% conf
                        </span>
                      )}
                    </div>
                  </div>
                </div>

                {/* Footer Action Buttons */}
                <div className="flex items-center justify-between mt-2 pt-1 border-t border-[#1b2530] text-[9px] font-mono">
                  <div className="text-[#869099]">
                    {alert.heading && <span>{alert.heading}</span>}
                  </div>

                  <div className="flex items-center gap-1.5">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onReplayEvent?.(alert);
                      }}
                      className="px-2 py-0.5 bg-[#33f0b4]/10 hover:bg-[#33f0b4]/25 text-[#33f0b4] border border-[#33f0b4]/30 rounded font-mono text-[8.5px] flex items-center gap-1 transition-colors cursor-pointer"
                      title="Replay incident event from beginning"
                    >
                      <PlayCircle size={10} />
                      <span>REPLAY</span>
                    </button>

                    {!alert.is_acknowledged ? (
                      <button
                        type="button"
                        onClick={(e) =>
                          handleAcknowledge(e, alert.event_id || alert.alert_id || "")
                        }
                        className="px-2 py-0.5 bg-[#33f0b4]/10 hover:bg-[#33f0b4]/20 text-[#33f0b4] border border-[#33f0b4]/40 rounded font-bold flex items-center gap-1 transition-colors cursor-pointer"
                      >
                        <Check size={10} />
                        <span>ACK</span>
                      </button>
                    ) : (
                      <span className="text-[#869099] flex items-center gap-0.5 px-1.5 py-0.5">
                        <Check size={10} /> ACKED
                      </span>
                    )}

                    <button
                      type="button"
                      onClick={() => onInspectAlert?.(alert)}
                      className="px-2 py-0.5 bg-[#070a0f] hover:bg-white/5 text-[#cbd5e1] hover:text-white border border-[#1b2530] rounded flex items-center gap-0.5 transition-colors cursor-pointer"
                    >
                      <span>INSPECT</span>
                      <ChevronRight size={10} />
                    </button>
                  </div>
                </div>
              </article>
            );
          })
        )}
      </div>
    </div>
  );
};
