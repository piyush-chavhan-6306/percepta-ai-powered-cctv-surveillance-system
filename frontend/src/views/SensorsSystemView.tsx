import React, { useState, useEffect } from "react";
import type { AuditLogEntry, DatabaseDiagnostics, MultiModalSensorsStatus } from "../types/surveillance";
import { api } from "../api/client";
import {
  Cpu,
  Radio,
  Database,
  CheckCircle,
  Clock,
  Send,
} from "lucide-react";

export const SensorsSystemView: React.FC = () => {
  const [sensorsStatus, setSensorsStatus] = useState<MultiModalSensorsStatus | null>(null);
  const [dbDiag, setDbDiag] = useState<DatabaseDiagnostics | null>(null);
  const [auditLogs, setAuditLogs] = useState<AuditLogEntry[]>([]);
  const [sensorSuccessMsg, setSensorSuccessMsg] = useState<string | null>(null);

  // Sensor Ingest Simulator Form State
  const [sensorType, setSensorType] = useState<string>("RADAR");
  const [sensorId, setSensorId] = useState<string>("RADAR_ALPHA_01");
  const [sectorId] = useState<string>("Sector Alpha");
  const [confidence, setConfidence] = useState<number>(0.95);
  const [rangeMeters, setRangeMeters] = useState<number>(340.5);
  const [velocityMps, setVelocityMps] = useState<number>(12.4);

  const loadData = async () => {
    try {
      const [sRes, dbRes, logsRes] = await Promise.allSettled([
        api.getSensorsStatus(),
        api.getDbDiagnostics(),
        api.getAuditLogs(30),
      ]);

      if (sRes.status === "fulfilled") setSensorsStatus(sRes.value);
      if (dbRes.status === "fulfilled") setDbDiag(dbRes.value);
      if (logsRes.status === "fulfilled") setAuditLogs(logsRes.value.audit_logs || []);
    } catch (err) {
      console.error("Failed to load sensor/system data:", err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleSimulateSensor = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await api.ingestSensorEvent({
        sensor_id: sensorId,
        sensor_type: sensorType,
        sector_id: sectorId,
        confidence,
        data: {
          range_meters: rangeMeters,
          velocity_mps: velocityMps,
          simulated: true,
        },
      });

      setSensorSuccessMsg(`Telemetry ingested from ${sensorId}!`);
      setTimeout(() => setSensorSuccessMsg(null), 3000);
      await loadData();
    } catch (err) {
      console.error("Sensor ingestion failed:", err);
    }
  };

  return (
    <div>
      <div className="panel-header" style={{ marginBottom: "1.25rem" }}>
        <div className="panel-title" style={{ fontSize: "1.1rem" }}>
          <Cpu size={20} color="var(--accent-cyan)" />
          Multi-Modal Sensor Integration & Platform Health Diagnostics
        </div>
        <button onClick={loadData} className="btn btn-secondary btn-sm">
          Refresh Diagnostics
        </button>
      </div>

      {sensorSuccessMsg && (
        <div style={{ background: "rgba(16, 185, 129, 0.15)", border: "1px solid rgba(16, 185, 129, 0.3)", color: "#34d399", padding: "0.6rem 1rem", borderRadius: "4px", marginBottom: "1rem", fontSize: "0.85rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
          <CheckCircle size={16} /> {sensorSuccessMsg}
        </div>
      )}

      {/* 2-Column Split: Multi-Modal Sensors vs Database Health */}
      <div style={{ display: "grid", gridTemplateColumns: "1.1fr 0.9fr", gap: "1.25rem", marginBottom: "1.25rem" }}>
        {/* Multi-Modal Sensors Panel */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title" style={{ fontSize: "0.88rem" }}>
              <Radio size={16} color="var(--accent-cyan)" /> Defense Multi-Modal Sensors
            </div>
            <span className="badge badge-zinc">
              {sensorsStatus?.total_sensors || 3} CHANNELS
            </span>
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", marginBottom: "1.25rem" }}>
            {sensorsStatus &&
              Object.entries(sensorsStatus.sensors).map(([sId, info]) => (
                <div
                  key={sId}
                  style={{
                    background: "#080c14",
                    border: "1px solid var(--border-subtle)",
                    padding: "0.65rem 0.85rem",
                    borderRadius: "4px",
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                  }}
                >
                  <div>
                    <div style={{ fontWeight: 700, fontSize: "0.82rem", color: "#f8fafc", fontFamily: "var(--font-mono)" }}>
                      {sId}
                    </div>
                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                      Sector: {info.sector} | Type: {info.type}
                    </div>
                  </div>
                  <span className="badge badge-green">ACTIVE</span>
                </div>
              ))}
          </div>

          {/* Sensor Telemetry Ingestion Simulator Form */}
          <div style={{ borderTop: "1px solid var(--border-subtle)", paddingTop: "1rem" }}>
            <div className="hud-label" style={{ marginBottom: "0.6rem" }}>
              Simulate External Sensor Telemetry Ingest
            </div>

            <form onSubmit={handleSimulateSensor} style={{ display: "flex", flexDirection: "column", gap: "0.6rem" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.5rem" }}>
                <div>
                  <label className="hud-label">Sensor Channel</label>
                  <select value={sensorType} onChange={(e) => setSensorType(e.target.value)} className="select" style={{ fontSize: "0.78rem" }}>
                    <option value="RADAR">Radar Tracker</option>
                    <option value="SEISMIC">Ground Seismic Sensor</option>
                    <option value="THERMAL_IR">Thermal Infrared</option>
                    <option value="RF_DETECTOR">RF Spectrum Detector</option>
                  </select>
                </div>
                <div>
                  <label className="hud-label">Sensor Identifier</label>
                  <input
                    type="text"
                    value={sensorId}
                    onChange={(e) => setSensorId(e.target.value)}
                    className="input"
                    style={{ fontSize: "0.78rem" }}
                  />
                </div>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.5rem" }}>
                <div>
                  <label className="hud-label">Target Range (m)</label>
                  <input
                    type="number"
                    value={rangeMeters}
                    onChange={(e) => setRangeMeters(Number(e.target.value))}
                    className="input"
                    style={{ fontSize: "0.78rem" }}
                  />
                </div>
                <div>
                  <label className="hud-label">Velocity (m/s)</label>
                  <input
                    type="number"
                    value={velocityMps}
                    onChange={(e) => setVelocityMps(Number(e.target.value))}
                    className="input"
                    style={{ fontSize: "0.78rem" }}
                  />
                </div>
                <div>
                  <label className="hud-label">Confidence</label>
                  <input
                    type="number"
                    step="0.05"
                    min="0"
                    max="1"
                    value={confidence}
                    onChange={(e) => setConfidence(Number(e.target.value))}
                    className="input"
                    style={{ fontSize: "0.78rem" }}
                  />
                </div>
              </div>

              <button type="submit" className="btn btn-secondary btn-sm" style={{ alignSelf: "flex-end" }}>
                <Send size={12} /> Ingest Telemetry
              </button>
            </form>
          </div>
        </div>

        {/* Database Health & PostgreSQL Migration Readiness */}
        <div className="panel">
          <div className="panel-header">
            <div className="panel-title" style={{ fontSize: "0.88rem" }}>
              <Database size={16} color="var(--accent-purple)" /> Storage Engine & Migration Readiness
            </div>
          </div>

          {dbDiag ? (
            <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.65rem" }}>
                <div className="hud-card">
                  <div className="hud-label">Storage Engine</div>
                  <div className="hud-value" style={{ fontSize: "1.1rem", color: "var(--accent-cyan)" }}>
                    SQLite WAL
                  </div>
                  <div className="hud-sub">Journal: {dbDiag.journal_mode}</div>
                </div>

                <div className="hud-card">
                  <div className="hud-label">Storage Footprint</div>
                  <div className="hud-value" style={{ fontSize: "1.1rem" }}>
                    {dbDiag.total_storage_mb} MB
                  </div>
                  <div className="hud-sub">WAL: {dbDiag.wal_file_size_mb} MB</div>
                </div>
              </div>

              {/* PostgreSQL Migration Certification Box */}
              <div
                style={{
                  background: "#080c14",
                  border: "1px solid rgba(16, 185, 129, 0.3)",
                  borderRadius: "6px",
                  padding: "0.85rem",
                }}
              >
                <div style={{ display: "flex", alignItems: "center", gap: "0.4rem", color: "#34d399", fontWeight: 700, fontSize: "0.8rem", marginBottom: "0.4rem" }}>
                  <CheckCircle size={14} /> ENTERPRISE POSTGRESQL MIGRATION CERTIFICATION
                </div>
                <div style={{ fontSize: "0.75rem", color: "var(--text-secondary)", lineHeight: 1.5 }}>
                  <div>• <strong>ORM Architecture:</strong> {dbDiag.enterprise_migration.orm_layer}</div>
                  <div>• <strong>SQL Dialect Locks:</strong> {dbDiag.enterprise_migration.dialect_locks}</div>
                  <div>• <strong>Migration Path:</strong> {dbDiag.enterprise_migration.migration_complexity}</div>
                </div>
              </div>
            </div>
          ) : (
            <div style={{ color: "var(--text-muted)", fontSize: "0.8rem", padding: "1.5rem", textAlign: "center" }}>
              Loading database diagnostics...
            </div>
          )}
        </div>
      </div>

      {/* Administrative Audit Trail Table */}
      <div className="panel">
        <div className="panel-header">
          <div className="panel-title" style={{ fontSize: "0.88rem" }}>
            <Clock size={15} color="var(--accent-amber)" /> Administrative System Action Audit Log ({auditLogs.length})
          </div>
        </div>

        <div className="table-container" style={{ maxHeight: "250px", overflowY: "auto" }}>
          <table className="table">
            <thead>
              <tr>
                <th>Timestamp</th>
                <th>Actor Callsign</th>
                <th>Administrative Action</th>
                <th>Action Payload Details</th>
              </tr>
            </thead>
            <tbody>
              {auditLogs.length === 0 ? (
                <tr>
                  <td colSpan={4} style={{ textAlign: "center", color: "var(--text-muted)", padding: "1.5rem" }}>
                    No administrative audit events recorded yet.
                  </td>
                </tr>
              ) : (
                auditLogs.map((log) => (
                  <tr key={log.audit_id}>
                    <td style={{ whiteSpace: "nowrap", fontFamily: "var(--font-mono)", fontSize: "0.72rem" }}>
                      {new Date(log.timestamp).toLocaleString()}
                    </td>
                    <td style={{ color: "var(--accent-cyan)", fontWeight: 600 }}>{log.actor}</td>
                    <td>
                      <span className="badge badge-zinc">{log.action}</span>
                    </td>
                    <td style={{ fontFamily: "var(--font-mono)", fontSize: "0.72rem", color: "var(--text-secondary)" }}>
                      {JSON.stringify(log.details)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
