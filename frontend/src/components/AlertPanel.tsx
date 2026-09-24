import { useEffect, useState } from "react";
import { AlertItem } from "@/types/surveillance";
import { api } from "@/api/client";
import { useWebSocket, WsMessage } from "@/hooks/useWebSocket";
import {
  AlertTriangle,
  ShieldAlert,
  Check,
  Filter,
  RefreshCw,
  ChevronRight,
  Clock,
  Compass,
  PlayCircle,
  Camera,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface AlertPanelProps {
  onSelectAlert?: (alert: AlertItem) => void;
  selectedAlertId?: string;
  onSeekTime?: (timestamp: string | number, cameraId?: string) => void;
  onAlertCountChange?: (count: number) => void;
}

function formatAlertTime(ts: string | number): string {
  try {
    const d = typeof ts === "number" ? new Date(ts) : new Date(ts);
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
}

export function AlertPanel({ onSelectAlert, selectedAlertId, onSeekTime, onAlertCountChange }: AlertPanelProps) {
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [filterSeverity, setFilterSeverity] = useState<string>("ALL");

  const fetchAlerts = async () => {
    try {
      setLoading(true);
      const res = await api.getAlerts({ limit: 50 });
      const fetched = res.alerts || [];
      setAlerts(fetched);
      onAlertCountChange?.(fetched.filter((a) => !a.is_acknowledged).length);
    } catch (err) {
      console.error("Failed to load alert history:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchAlerts();
  }, []);

  // Listen to live WebSocket events (real-time push)
  useWebSocket((msg: WsMessage) => {
    const evType = String(msg.event_type || "").toUpperCase();
    if (evType === "ALERT" || evType === "ZONE" || evType === "INCIDENT") {
      const isZone = evType === "ZONE";
      const severity = String(msg.severity || (isZone ? (msg as any).zone_severity : "CRITICAL") || "CRITICAL").toUpperCase();
      const message =
        msg.message ||
        (isZone
          ? `ZONE INTRUSION: Track #${msg.track_id ?? "?"} ${(msg as any).transition ?? "entered"} ${(msg as any).zone_name ?? "Restricted Area"}`
          : "Security perimeter violation detected");

      const newAlert: AlertItem = {
        event_id: String(msg.event_id || `alert-${Date.now()}`),
        alert_id: String(msg.alert_id || msg.event_id || `alert-${Date.now()}`),
        timestamp: msg.timestamp || new Date().toISOString(),
        camera_id: msg.camera_id || "CAM-01",
        track_id: msg.track_id ? String(msg.track_id) : undefined,
        incident_id: msg.incident_id ? String(msg.incident_id) : undefined,
        severity,
        message,
        confidence: msg.confidence ?? 0.92,
        is_acknowledged: false,
        threat_score: (msg as any).threat_score ?? (severity === "CRITICAL" ? 85 : 55),
        threat_level: (msg as any).threat_level ?? (severity === "CRITICAL" ? "CRITICAL" : "RESTRICTED"),
        threat_reasons: (msg as any).threat_reasons ?? [(msg as any).narrative ?? message],
        causal_chain: (msg as any).causal_chain,
        evidence_snapshot_uri: (msg as any).evidence_snapshot_uri,
        face_snapshot_uri: (msg as any).face_snapshot_uri,
        anpr_snapshot_uri: (msg as any).anpr_snapshot_uri,
      };

      setAlerts((prev) => {
        if (prev.some((a) => a.event_id === newAlert.event_id || a.alert_id === newAlert.alert_id)) {
          return prev;
        }
        const updated = [newAlert, ...prev.slice(0, 99)];
        onAlertCountChange?.(updated.filter((a) => !a.is_acknowledged).length);
        return updated;
      });
    }
  });

  const handleAcknowledge = async (e: React.MouseEvent, alertId: string) => {
    e.stopPropagation();
    try {
      await api.acknowledgeAlert(alertId);
      setAlerts((prev) =>
        prev.map((a) => (a.event_id === alertId || a.alert_id === alertId ? { ...a, is_acknowledged: true } : a))
      );
    } catch (err) {
      console.error("Failed to acknowledge alert:", err);
    }
  };

  const handleTimelineSeek = (e: React.MouseEvent, alert: AlertItem) => {
    e.stopPropagation();
    if (onSeekTime) {
      onSeekTime(alert.timestamp, alert.camera_id);
    }
    if (onSelectAlert) {
      onSelectAlert(alert);
    }
  };

  const filteredAlerts = alerts.filter((a) => {
    if (filterSeverity === "ALL") return true;
    return a.severity?.toUpperCase() === filterSeverity;
  });

  const unacknowledgedCount = alerts.filter((a) => !a.is_acknowledged).length;

  return (
    <div className="flex flex-col h-full min-h-0">
      {/* Header */}
      <div className="p-3.5 border-b border-[rgba(30,41,59,0.4)] flex items-center justify-between bg-[rgba(5,7,10,0.5)]">
        <div className="flex items-center gap-2">
          <div className="relative">
            <ShieldAlert className="w-4 h-4 text-[#ff5252]" />
            {unacknowledgedCount > 0 && (
              <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-[#ff1744] animate-ping" />
            )}
          </div>
          <h2 className="text-xs font-bold text-foreground font-mono uppercase tracking-wider">
            TACTICAL INCIDENT FEED
          </h2>
          <span className="px-1.5 py-0.5 text-[10px] font-mono bg-[rgba(255,23,68,0.12)] text-[#ff5252] border border-[rgba(255,23,68,0.25)] rounded-md">
            {unacknowledgedCount} ACTIVE
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <select
            value={filterSeverity}
            onChange={(e) => setFilterSeverity(e.target.value)}
            className="bg-black/60 border border-white/10 rounded-md px-2 py-1 text-[10px] font-mono text-muted-foreground focus:outline-none"
          >
            <option value="ALL">ALL SEVERITY</option>
            <option value="CRITICAL">CRITICAL</option>
            <option value="RESTRICTED">RESTRICTED</option>
            <option value="NORMAL">NORMAL</option>
          </select>
          <Button
            variant="ghost"
            size="icon"
            onClick={fetchAlerts}
            className="h-7 w-7 text-[#6b7a99] hover:text-foreground"
            title="Refresh feed"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </Button>
        </div>
      </div>

      {/* Alert List */}
      <div
        className="flex-1 min-h-0 overflow-y-auto divide-y divide-white/5 pr-1"
        style={{
          scrollbarWidth: 'thin',
          scrollbarColor: 'rgba(255,255,255,0.3) transparent',
        }}
      >
        {filteredAlerts.length === 0 ? (              <div className="flex flex-col items-center justify-center h-48 text-center p-4">
            <ShieldAlert className="w-8 h-8 text-[#2d3748] mb-2" />
            <p className="text-xs text-[#6b7a99] font-mono">NO ACTIVE INCIDENTS IN SECTOR</p>
            <p className="text-[10px] text-[#4a5568] mt-1">Perimeter status normal</p>
          </div>
        ) : (
          filteredAlerts.map((alert) => {
            const isSelected = selectedAlertId === alert.event_id || selectedAlertId === alert.alert_id;
            const sevUpper = (alert.severity || "NORMAL").toUpperCase();
            const isCrit = sevUpper === "CRITICAL";
            const isRestricted = sevUpper === "RESTRICTED";
            const threatScore = alert.threat_score ?? (isCrit ? 85 : isRestricted ? 50 : 15);

            return (
              <div
                key={alert.event_id || alert.alert_id}
                onClick={() => onSelectAlert?.(alert)}
                className={`p-3 transition-all cursor-pointer relative group ${
                  isSelected
                    ? "bg-primary/10 border-l-4 border-l-primary"
                    : alert.is_acknowledged
                    ? "opacity-60 hover:opacity-100 hover:bg-white/[0.03]"
                    : "hover:bg-white/[0.04] border-l-2 border-l-transparent"
                }`}
              >
                <div className="flex items-start justify-between gap-2 mb-1.5">
                  <div className="flex items-center gap-1.5 flex-wrap">
                    <span
                      className={`text-[9px] font-mono px-2 py-0.5 uppercase rounded-full border font-bold ${
                        isCrit
                          ? "bg-[rgba(255,23,68,0.12)] text-[#ff5252] border-[rgba(255,23,68,0.3)]"
                          : isRestricted
                          ? "bg-[rgba(255,109,0,0.12)] text-[#ff9100] border-[rgba(255,109,0,0.3)]"
                          : "bg-[rgba(0,230,118,0.1)] text-[#00e676] border-[rgba(0,230,118,0.25)]"
                      }`}
                    >
                      {sevUpper}
                    </span>

                    {/* Threat Score Badge */}
                    <span
                      className={`text-[9px] font-mono px-1.5 py-0.5 rounded border font-semibold ${
                        threatScore >= 75
                          ? "bg-[rgba(255,23,68,0.15)] text-[#ff8a80] border-[rgba(255,23,68,0.3)]"
                          : threatScore >= 50
                          ? "bg-[rgba(255,109,0,0.15)] text-[#ffab91] border-[rgba(255,109,0,0.3)]"
                          : "bg-[rgba(255,171,0,0.15)] text-[#ffe082] border-[rgba(255,171,0,0.3)]"
                      }`}
                    >
                      THREAT {threatScore}/100
                    </span>

                    <span className="text-[10px] font-mono text-[#00e5ff] flex items-center gap-1">
                      <Camera className="w-2.5 h-2.5" />
                      {alert.camera_id}
                    </span>

                    {alert.track_id && (
                      <span className="text-[10px] font-mono text-muted-foreground">
                        TRACK #{alert.track_id}
                      </span>
                    )}
                  </div>

                  {/* Clickable Timestamp with Timeline Seek Action */}
                  <button
                    onClick={(e) => handleTimelineSeek(e, alert)}
                    className="flex items-center gap-1 text-[10px] font-mono text-[#00e5ff] hover:text-[#80f0ff] bg-[rgba(0,229,255,0.06)] hover:bg-[rgba(0,229,255,0.12)] border border-[rgba(0,229,255,0.15)] px-1.5 py-0.5 rounded transition-colors group/btn"
                    title="Click to seek video timeline to event moment"
                  >
                    <PlayCircle className="w-3 h-3 text-[#00e5ff] group-hover/btn:scale-110 transition-transform" />
                    <span>{formatAlertTime(alert.timestamp)}</span>
                  </button>
                </div>

                <p className="text-xs text-foreground font-medium line-clamp-2 leading-tight">
                  {alert.message || alert.reason || "Perimeter anomaly detected"}
                </p>

                {/* Footer telemetry */}
                <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-muted-foreground">
                  <div className="flex items-center gap-2">
                    {alert.heading && (
                      <span className="flex items-center gap-0.5 text-blue-400">
                        <Compass className="w-2.5 h-2.5" />
                        {alert.heading}
                      </span>
                    )}
                    {alert.speed_description && (
                      <span className="text-muted-foreground/80">{alert.speed_description}</span>
                    )}
                  </div>

                  <div className="flex items-center gap-2">
                    {!alert.is_acknowledged ? (
                      <button
                        onClick={(e) => handleAcknowledge(e, alert.event_id || alert.alert_id || "")}
                        className="text-[9px] text-[#00e676] hover:text-[#69f0ae] flex items-center gap-0.5 px-1.5 py-0.5 rounded bg-[rgba(0,230,118,0.08)] border border-[rgba(0,230,118,0.15)]"
                      >
                        <Check className="w-2.5 h-2.5" /> ACK
                      </button>
                    ) : (
                      <span className="text-[9px] text-muted-foreground flex items-center gap-0.5">
                        <Check className="w-2.5 h-2.5" /> ACKED
                      </span>
                    )}
                    <ChevronRight className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary transition-colors" />
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
