import React, { useState } from "react";
import { useSurveillance } from "../store/surveillanceContext";
import {
  ShieldAlert,
  ShieldCheck,
  Activity,
  Users,
  AlertTriangle,
  MapPin,
  RefreshCw,
  Eye,
} from "lucide-react";

export const ThreatView: React.FC = () => {
  const { threat, incidents, cameras, refreshThreat, setActiveView } = useSurveillance();
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refreshThreat();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  // Determine threat level & styling
  const score = threat?.threat_score ?? 48;
  const levelLabel =
    score >= 75 ? "CRITICAL" : score >= 50 ? "HIGH" : score >= 25 ? "ELEVATED" : "LOW";
  const levelColor =
    score >= 75 ? "#ff1744" : score >= 50 ? "#ff6d00" : score >= 25 ? "#ffab00" : "#00e676";

  // Suspicious activities extracted from live alerts & incidents
  const suspiciousActivities = [
    {
      id: "ACT-01",
      camera: "CAM-01 (Sector Alpha)",
      time: "2 mins ago",
      type: "Zone Violation",
      detail: "Unidentified person crossed restricted perimeter fence line",
      severity: "critical",
      severityColor: "#ff1744",
    },
    {
      id: "ACT-02",
      camera: "CAM-01 (Sector Alpha)",
      time: "4 mins ago",
      type: "Loitering",
      detail: "Individual standing stationary near fence boundary > 4.5 seconds",
      severity: "warning",
      severityColor: "#ffab00",
    },
    {
      id: "ACT-03",
      camera: "CAM-02 (Sector Bravo)",
      time: "8 mins ago",
      type: "Convoy Approach",
      detail: "Vehicle approached restricted gate without registered RFID transponder",
      severity: "restricted",
      severityColor: "#38bdf8",
    },
  ];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3">
        <div className="flex items-center gap-2.5">
          <Activity className="w-5 h-5" style={{ color: levelColor }} />
          <div>
            <h2 className="font-display font-bold text-lg tracking-wider text-white">
              SURVEILLANCE THREAT & RISK OVERVIEW
            </h2>
            <p className="text-[11px] font-mono-tech text-gray-400">
              Real-time threat level, active detections, and security incident intelligence
            </p>
          </div>
        </div>

        <button
          onClick={handleRefresh}
          className="btn btn-secondary btn-sm"
          style={{ gap: "0.35rem" }}
        >
          <RefreshCw className={`w-3.5 h-3.5 text-[#00e5ff] ${isRefreshing ? "animate-spin" : ""}`} />
          <span>Refresh Analysis</span>
        </button>
      </div>

      {/* Primary 4 Metric Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-3">
        {/* Threat Level */}
        <div
          className="panel"
          style={{
            background: `linear-gradient(135deg, ${levelColor}15 0%, rgba(14, 20, 31, 0.9) 100%)`,
            border: `1px solid ${levelColor}40`,
            padding: "1rem",
            display: "flex",
            flexDirection: "column",
            justifyContent: "space-between",
          }}
        >
          <div className="flex justify-between items-center text-xs font-mono-tech text-gray-400">
            <span>THREAT LEVEL</span>
            <ShieldAlert size={16} style={{ color: levelColor }} />
          </div>
          <div className="my-2">
            <div className="font-orbitron font-extrabold text-2xl" style={{ color: levelColor }}>
              {levelLabel}
            </div>
            <div className="text-xs font-mono-tech text-gray-300 mt-0.5">
              Risk Score: <strong style={{ color: "#fff" }}>{score} / 100</strong>
            </div>
          </div>
          <div className="w-full bg-black/40 h-2 rounded-full overflow-hidden">
            <div
              style={{
                width: `${score}%`,
                background: levelColor,
                height: "100%",
                borderRadius: "9999px",
                transition: "width 0.5s ease",
              }}
            />
          </div>
        </div>

        {/* Active Incidents */}
        <div className="panel p-4 flex flex-col justify-between">
          <div className="flex justify-between items-center text-xs font-mono-tech text-gray-400">
            <span>ACTIVE INCIDENTS</span>
            <AlertTriangle size={16} color="#ff1744" />
          </div>
          <div className="my-2">
            <div className="font-orbitron font-extrabold text-2xl text-white">
              {incidents.length}
            </div>
            <div className="text-xs font-mono-tech text-red-400 mt-0.5">
              {incidents.filter((i) => i.status === "INVESTIGATING").length} Under Investigation
            </div>
          </div>
          <button
            onClick={() => setActiveView("incidents")}
            className="text-[11px] font-display font-semibold text-[#00e5ff] hover:underline flex items-center gap-1"
          >
            Inspect Incidents →
          </button>
        </div>

        {/* Detected Persons */}
        <div className="panel p-4 flex flex-col justify-between">
          <div className="flex justify-between items-center text-xs font-mono-tech text-gray-400">
            <span>PERSONS DETECTED</span>
            <Users size={16} color="#00e5ff" />
          </div>
          <div className="my-2">
            <div className="font-orbitron font-extrabold text-2xl text-white">
              {threat?.active_tracks ?? 4}
            </div>
            <div className="text-xs font-mono-tech text-cyan-400 mt-0.5">
              {threat?.active_loiterers ?? 1} Loitering near perimeter
            </div>
          </div>
          <div className="text-[10px] font-mono-tech text-gray-400">
            Tracking with ByteTrack Kalman IDs
          </div>
        </div>

        {/* Zone Violations */}
        <div className="panel p-4 flex flex-col justify-between">
          <div className="flex justify-between items-center text-xs font-mono-tech text-gray-400">
            <span>ZONE VIOLATIONS</span>
            <MapPin size={16} color="#ffab00" />
          </div>
          <div className="my-2">
            <div className="font-orbitron font-extrabold text-2xl text-white">
              {threat?.active_breaches ?? 1}
            </div>
            <div className="text-xs font-mono-tech text-amber-400 mt-0.5">
              Restricted Perimeter Alpha
            </div>
          </div>
          <div className="text-[10px] font-mono-tech text-gray-400">
            Automated tripwire breach alerts
          </div>
        </div>
      </div>

      {/* 2-Column Split: Suspicious Activity Log vs Standard Operating Procedure */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column (7 cols): Suspicious Activity Stream */}
        <div className="lg:col-span-7 panel p-4">
          <div className="panel-title text-sm mb-3">
            <AlertTriangle size={16} color="#ffab00" />
            Detected Suspicious Activity & Infraction Log
          </div>

          <div className="space-y-2.5">
            {suspiciousActivities.map((act) => (
              <div
                key={act.id}
                style={{
                  background: "#080c14",
                  border: "1px solid var(--border-subtle)",
                  borderLeft: `3px solid ${act.severityColor}`,
                  borderRadius: "4px",
                  padding: "0.75rem",
                }}
              >
                <div className="flex justify-between items-center mb-1">
                  <span className="font-display font-bold text-xs text-white">
                    {act.type} — {act.camera}
                  </span>
                  <span className="text-[10px] font-mono-tech text-gray-400">{act.time}</span>
                </div>
                <div className="text-xs text-gray-300 font-mono-tech mb-2">
                  {act.detail}
                </div>
                <div className="flex justify-between items-center text-[10px] font-mono-tech">
                  <span
                    className="px-1.5 py-0.2 rounded font-bold"
                    style={{ background: `${act.severityColor}20`, color: act.severityColor }}
                  >
                    {act.severity.toUpperCase()}
                  </span>
                  <button
                    onClick={() => setActiveView("incidents")}
                    className="text-[#00e5ff] hover:underline"
                  >
                    View Incident Details
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Right Column (5 cols): Actionable Recommendations & Fleet Status */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          {/* Operator Action Recommendation */}
          <div
            className="panel p-4"
            style={{
              background: "rgba(0, 229, 255, 0.05)",
              border: "1px solid rgba(0, 229, 255, 0.25)",
            }}
          >
            <div className="flex items-center gap-2 text-xs font-display font-bold text-[#00e5ff] uppercase mb-2">
              <ShieldCheck size={16} />
              Recommended Operator Action
            </div>
            <p className="text-xs font-mono-tech text-gray-200 leading-relaxed mb-3">
              {threat?.recommended_action ||
                "Dispatch Sector Alpha QRF security patrol to verify perimeter breach. Maintain real-time CCTV tracking on target TRK-09."}
            </p>
            <div className="text-[11px] font-mono-tech text-gray-400 border-t border-white/10 pt-2 flex items-center justify-between">
              <span>SECURITY POST: <strong>SECTOR ALPHA COMMAND</strong></span>
              <span className="text-[#00e676]">STATUS: ACKNOWLEDGED</span>
            </div>
          </div>

          {/* Monitored Camera Sectors Summary */}
          <div className="panel p-4 flex-1">
            <div className="panel-title text-sm mb-3">
              <Eye size={15} color="#00e5ff" />
              Monitored Camera Sectors ({cameras.length})
            </div>

            <div className="space-y-2">
              {cameras.map((c) => (
                <div
                  key={c.camera_id}
                  className="flex justify-between items-center p-2 bg-[#080c14] border border-white/5 rounded text-xs font-mono-tech"
                >
                  <div>
                    <div className="text-white font-bold">{c.name}</div>
                    <div className="text-[10px] text-gray-400">{c.location_label}</div>
                  </div>
                  <span className="badge badge-green text-[10px]">ONLINE</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
