import React from "react";
import type { AlertItem } from "../types/surveillance";
import { useSurveillance } from "../store/surveillanceContext";
import { CheckCircle, ShieldAlert, Clock, Camera } from "lucide-react";

interface AlertTickerProps {
  alerts?: AlertItem[];
  limit?: number;
}

export const AlertTicker: React.FC<AlertTickerProps> = ({ alerts: propAlerts, limit = 15 }) => {
  const { alerts: storeAlerts, acknowledgeAlert } = useSurveillance();
  const alertsToDisplay = (propAlerts || storeAlerts).slice(0, limit);

  const getSeverityBadge = (severity?: string) => {
    const s = (severity || "restricted").toUpperCase();
    switch (s) {
      case "CRITICAL":
        return <span className="badge badge-red">CRITICAL</span>;
      case "RESTRICTED":
        return <span className="badge badge-orange">RESTRICTED</span>;
      case "WARNING":
        return <span className="badge badge-yellow">WARNING</span>;
      default:
        return <span className="badge badge-zinc">INFO</span>;
    }
  };

  return (
    <div className="panel" style={{ height: "100%", display: "flex", flexDirection: "column" }}>
      <div className="panel-header">
        <div className="panel-title">
          <ShieldAlert size={16} color="var(--accent-crimson)" />
          Live Security Alerts Stream
        </div>
        <span className="badge badge-zinc">{alertsToDisplay.length} RECENT</span>
      </div>

      <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
        {alertsToDisplay.length === 0 ? (
          <div style={{ textAlign: "center", padding: "2rem", color: "var(--text-muted)", fontSize: "0.85rem" }}>
            <CheckCircle size={32} color="#10b981" style={{ margin: "0 auto 0.5rem" }} />
            No active perimeter breach alerts detected. Sector baseline nominal.
          </div>
        ) : (
          alertsToDisplay.map((alert) => (
            <div
              key={alert.event_id}
              style={{
                background: alert.is_acknowledged ? "#0e131d" : "#161e2e",
                border: "1px solid",
                borderColor: alert.is_acknowledged ? "var(--border-subtle)" : "rgba(239, 68, 68, 0.3)",
                borderRadius: "4px",
                padding: "0.65rem 0.75rem",
                display: "flex",
                justifyContent: "space-between",
                alignItems: "flex-start",
                gap: "0.75rem",
                transition: "all 0.15s ease",
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", marginBottom: "0.3rem" }}>
                  {getSeverityBadge(alert.severity)}
                  <span style={{ fontSize: "0.72rem", color: "var(--text-secondary)", fontFamily: "var(--font-mono)", display: "flex", alignItems: "center", gap: "0.25rem" }}>
                    <Camera size={11} /> {alert.camera_id}
                  </span>
                  {alert.track_id && (
                    <span style={{ fontSize: "0.72rem", color: "var(--accent-cyan)", fontFamily: "var(--font-mono)" }}>
                      TRACK #{alert.track_id}
                    </span>
                  )}
                  <span style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginLeft: "auto", display: "flex", alignItems: "center", gap: "0.25rem" }}>
                    <Clock size={11} /> {new Date(alert.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <div style={{ fontSize: "0.82rem", color: alert.is_acknowledged ? "var(--text-secondary)" : "#ffffff", fontWeight: alert.is_acknowledged ? 400 : 600 }}>
                  {alert.message}
                </div>
              </div>

              {!alert.is_acknowledged && (
                <button
                  onClick={() => acknowledgeAlert(alert.event_id)}
                  className="btn btn-secondary btn-sm"
                  style={{ whiteSpace: "nowrap", alignSelf: "center" }}
                  title="Acknowledge alert"
                >
                  <CheckCircle size={12} /> Ack
                </button>
              )}
            </div>
          ))
        )}
      </div>
    </div>
  );
};
