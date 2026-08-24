import React from "react";
import type { IncidentDossier } from "../types/surveillance";
import { FileText, Shield, Compass, Activity, Key, X, Download } from "lucide-react";

interface DossierModalProps {
  dossier: IncidentDossier;
  onClose: () => void;
}

export const DossierModal: React.FC<DossierModalProps> = ({ dossier, onClose }) => {
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()} style={{ maxWidth: "850px", padding: "1.5rem" }}>
        {/* Header */}
        <div className="panel-header" style={{ marginBottom: "1.25rem" }}>
          <div className="panel-title" style={{ fontSize: "1.1rem" }}>
            <FileText size={20} color="var(--accent-cyan)" />
            Tactical Incident Forensic Dossier — {dossier.incident_id}
          </div>
          <button onClick={onClose} className="btn btn-secondary btn-sm">
            <X size={16} />
          </button>
        </div>

        {/* High-Level Overview Grid */}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "0.75rem", marginBottom: "1.25rem" }}>
          <div className="hud-card">
            <div className="hud-label">Incident Severity</div>
            <div style={{ marginTop: "0.35rem" }}>
              <span className={`badge ${dossier.severity === "CRITICAL" ? "badge-red" : "badge-orange"}`}>
                {dossier.severity}
              </span>
            </div>
          </div>
          <div className="hud-card">
            <div className="hud-label">Surveillance Sector</div>
            <div className="hud-value" style={{ fontSize: "1.1rem" }}>
              {dossier.camera_id}
            </div>
          </div>
          <div className="hud-card">
            <div className="hud-label">Duration</div>
            <div className="hud-value" style={{ fontSize: "1.1rem" }}>
              {dossier.duration_seconds.toFixed(1)}s
            </div>
          </div>
          <div className="hud-card">
            <div className="hud-label">Total Events Logged</div>
            <div className="hud-value" style={{ fontSize: "1.1rem" }}>
              {dossier.total_events_logged}
            </div>
          </div>
        </div>

        {/* Tactical SitRep Briefing Box */}
        <div
          style={{
            background: "#080c14",
            border: "1px solid var(--border-subtle)",
            borderRadius: "6px",
            padding: "1rem",
            marginBottom: "1.25rem",
          }}
        >
          <div style={{ fontSize: "0.8rem", fontWeight: 700, color: "var(--accent-cyan)", marginBottom: "0.5rem", display: "flex", alignItems: "center", gap: "0.4rem" }}>
            <Activity size={14} /> SITUATION REPORT (SITREP) SUMMARY
          </div>
          <div style={{ fontSize: "0.85rem", color: "var(--text-primary)", lineHeight: 1.6 }}>
            {dossier.tactical_sitrep}
          </div>
        </div>

        {/* Motion Profile & Infractions Split */}
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginBottom: "1.25rem" }}>
          {/* Motion Vector Metrics */}
          {dossier.motion_summary && (
            <div className="panel" style={{ padding: "1rem" }}>
              <div className="panel-title" style={{ fontSize: "0.85rem", marginBottom: "0.75rem" }}>
                <Compass size={14} color="var(--accent-cyan)" /> Target Motion Dynamics
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.4rem", fontSize: "0.8rem" }}>
                <div><strong>Target Classification:</strong> {dossier.motion_summary.target_class.toUpperCase()}</div>
                <div><strong>Net Spatial Displacement:</strong> {dossier.motion_summary.net_displacement_pixels.toFixed(1)} px</div>
                <div><strong>Average Velocity:</strong> {dossier.motion_summary.average_speed_pixels_per_frame.toFixed(1)} px/frame</div>
                {dossier.motion_summary.dominant_cardinal_direction && (
                  <div>
                    <strong>Heading Direction:</strong> {dossier.motion_summary.dominant_cardinal_direction} ({dossier.motion_summary.dominant_heading_degrees?.toFixed(0)}°)
                  </div>
                )}
                <div><strong>Trajectory Points Recorded:</strong> {dossier.motion_summary.total_trajectory_points}</div>
              </div>
            </div>
          )}

          {/* Infractions List */}
          <div className="panel" style={{ padding: "1rem" }}>
            <div className="panel-title" style={{ fontSize: "0.85rem", marginBottom: "0.75rem" }}>
              <Shield size={14} color="var(--accent-crimson)" /> Security Zone Infractions
            </div>
            <div style={{ maxHeight: "160px", overflowY: "auto", display: "flex", flexDirection: "column", gap: "0.35rem" }}>
              {dossier.infractions.length === 0 ? (
                <div style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>No zone boundary infractions recorded.</div>
              ) : (
                dossier.infractions.map((inf, i) => (
                  <div
                    key={i}
                    style={{
                      background: "#080c14",
                      padding: "0.4rem 0.6rem",
                      borderRadius: "4px",
                      fontSize: "0.75rem",
                      border: "1px solid var(--border-subtle)",
                    }}
                  >
                    <span style={{ color: "var(--accent-orange)", fontWeight: 600 }}>{inf.zone_name}</span>: {inf.transition_type.toUpperCase()}
                    {inf.dwell_duration_seconds !== undefined && ` (${inf.dwell_duration_seconds.toFixed(1)}s dwell)`}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Cryptographic SHA-256 Chain of Custody Token */}
        <div
          style={{
            background: "#0a0f1c",
            border: "1px solid var(--border-active)",
            borderRadius: "6px",
            padding: "0.75rem 1rem",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: "0.5rem",
          }}
        >
          <div>
            <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", fontWeight: 700, display: "flex", alignItems: "center", gap: "0.3rem" }}>
              <Key size={12} color="#10b981" /> FORENSIC SHA-256 AUDIT TOKEN
            </div>
            <div style={{ fontFamily: "var(--font-mono)", fontSize: "0.75rem", color: "#34d399", wordBreak: "break-all" }}>
              {dossier.forensic_hash}
            </div>
          </div>
          <button
            onClick={() => {
              const blob = new Blob([JSON.stringify(dossier, null, 2)], { type: "application/json" });
              const url = URL.createObjectURL(blob);
              const a = document.createElement("a");
              a.href = url;
              a.download = `DOSSIER_${dossier.incident_id}.json`;
              a.click();
            }}
            className="btn btn-secondary btn-sm"
          >
            <Download size={14} /> Download Dossier JSON
          </button>
        </div>
      </div>
    </div>
  );
};
