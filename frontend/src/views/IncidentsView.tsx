import React, { useState } from "react";
import {
  DEMO_INCIDENTS,
  getSeverityColor,
  formatTimestamp,
  type DemoIncident,
} from "../lib/demoData";
import {
  AlertTriangle,
  Shield,
  Clock,
  Check,
  ChevronRight,
  Eye,
  Camera,
  X,
  Filter,
  Download,
  Target,
  MapPin,
  Compass,
} from "lucide-react";

/* ═══════════════════════════════════════════════════════════════════
   INCIDENT DETAIL DRAWER
   Answers: WHAT, WHO, WHERE, WHEN, SEVERITY, WHY, EVIDENCE, STATUS, WHERE NOW?
   ═══════════════════════════════════════════════════════════════════ */
const IncidentDetail: React.FC<{
  incident: DemoIncident;
  onClose: () => void;
  onAcknowledge: (id: string) => void;
  onResolve: (id: string) => void;
}> = ({ incident, onClose, onAcknowledge, onResolve }) => {
  const severityColor = getSeverityColor(incident.severity);

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-end" onClick={onClose}>
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" />
      <div
        className="relative w-full max-w-xl h-full bg-[rgba(8,13,22,0.98)] border-l border-[rgba(255,255,255,0.1)] overflow-y-auto p-6 space-y-5 font-sans"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-start justify-between border-b border-[rgba(255,255,255,0.08)] pb-4">
          <div>
            <div className="flex items-center gap-2 mb-1.5 font-mono">
              <span
                className="px-2 py-0.5 rounded text-[9px] font-bold uppercase"
                style={{ backgroundColor: `${severityColor}20`, color: severityColor, border: `1px solid ${severityColor}40` }}
              >
                {incident.severity}
              </span>
              <span className="text-white font-bold text-xs">{incident.id}</span>
              <span className="text-[#64748b] text-[10px]">· 1 INCIDENT = 1 ALERT INVARIANT</span>
            </div>
            <h3 className="text-xl font-condensed font-bold text-white uppercase tracking-wide">
              {incident.description}
            </h3>
          </div>
          <button onClick={onClose} className="p-1.5 hover:bg-[rgba(255,255,255,0.05)] rounded text-[#94a3b8] hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* 9 Core Intelligence Answers */}
        <div className="grid grid-cols-2 gap-3 font-mono text-xs">
          <div className="p-3 rounded border border-[rgba(255,255,255,0.06)] bg-[rgba(5,7,10,0.8)]">
            <div className="text-[9px] text-[#64748b] uppercase mb-1">WHAT? (INCIDENT TYPE)</div>
            <div className="text-white font-bold">{incident.description}</div>
          </div>

          <div className="p-3 rounded border border-[rgba(255,255,255,0.06)] bg-[rgba(5,7,10,0.8)]">
            <div className="text-[9px] text-[#64748b] uppercase mb-1">WHO/WHAT? (TARGET ENTITY)</div>
            <div className="text-[#00e5ff] font-bold">GLOBAL-PERSON-042</div>
          </div>

          <div className="p-3 rounded border border-[rgba(255,255,255,0.06)] bg-[rgba(5,7,10,0.8)]">
            <div className="text-[9px] text-[#64748b] uppercase mb-1">WHERE? (SECTOR / CAMERA)</div>
            <div className="text-white">{incident.cameraId} · NORTH CORRIDOR</div>
          </div>

          <div className="p-3 rounded border border-[rgba(255,255,255,0.06)] bg-[rgba(5,7,10,0.8)]">
            <div className="text-[9px] text-[#64748b] uppercase mb-1">WHEN? (FIRST SEEN & DWELL)</div>
            <div className="text-white">{formatTimestamp(incident.firstSeen)}</div>
          </div>

          <div className="p-3 rounded border border-[rgba(255,255,255,0.06)] bg-[rgba(5,7,10,0.8)]">
            <div className="text-[9px] text-[#64748b] uppercase mb-1">SEVERITY? (DETERMINISTIC THREAT)</div>
            <div className="text-xl font-bold" style={{ color: severityColor }}>
              {incident.threatScore} <span className="text-xs text-[#64748b]">/ 100</span>
            </div>
          </div>

          <div className="p-3 rounded border border-[rgba(255,255,255,0.06)] bg-[rgba(5,7,10,0.8)]">
            <div className="text-[9px] text-[#64748b] uppercase mb-1">WHERE IS TARGET NOW?</div>
            <div className="text-[#00e676] font-bold flex items-center gap-1">
              <Compass className="w-3 h-3" /> CAM-03 (WESTBOUND)
            </div>
          </div>
        </div>

        {/* WHY? Contributing Factors */}
        <div className="p-4 rounded border border-[rgba(255,255,255,0.06)] bg-[rgba(5,7,10,0.8)] space-y-2">
          <div className="text-[9px] font-mono text-[#00e5ff] uppercase tracking-wider font-bold">
            WHY DID THREAT ESCALATE? (CONTRIBUTING FACTORS)
          </div>
          <div className="flex flex-wrap gap-2">
            {incident.factors.map((f, i) => (
              <span
                key={i}
                className="px-2.5 py-1 rounded text-[10px] font-mono border border-[rgba(0,229,255,0.25)] bg-[rgba(0,229,255,0.04)] text-[#00e5ff]"
              >
                ■ {f}
              </span>
            ))}
          </div>
        </div>

        {/* EVIDENCE? Target Crop Snapshot */}
        <div className="p-4 rounded border border-[rgba(0,229,255,0.2)] bg-[rgba(5,7,10,0.8)] space-y-3">
          <div className="flex items-center justify-between text-[9px] font-mono">
            <span className="text-[#00e5ff] font-bold uppercase">TARGET EVIDENCE CROP</span>
            <span className="text-[#00e676]">SHA-256 HASH VERIFIED</span>
          </div>
          <div className="aspect-[16/9] rounded border border-[rgba(0,229,255,0.2)] bg-[#05070a] relative overflow-hidden flex items-center justify-center">
            <div className="w-24 h-36 border-2 border-[#00e5ff] rounded relative flex items-end justify-center pb-1">
              <span className="text-[8px] font-mono bg-[#00e5ff] text-black px-1 font-bold">
                PERSON-042
              </span>
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        <div className="flex gap-3 pt-2 font-mono text-xs">
          {incident.status === "ACTIVE" && (
            <>
              <button
                onClick={() => onAcknowledge(incident.id)}
                className="flex-1 py-2.5 rounded bg-[rgba(0,230,118,0.12)] text-[#00e676] hover:bg-[#00e676] hover:text-black border border-[#00e67644] font-bold transition-all flex items-center justify-center gap-1.5"
              >
                <Check className="w-3.5 h-3.5" /> ACKNOWLEDGE
              </button>
              <button
                onClick={() => onResolve(incident.id)}
                className="flex-1 py-2.5 rounded bg-[rgba(0,229,255,0.12)] text-[#00e5ff] hover:bg-[#00e5ff] hover:text-black border border-[#00e5ff44] font-bold transition-all flex items-center justify-center gap-1.5"
              >
                <Shield className="w-3.5 h-3.5" /> RESOLVE
              </button>
            </>
          )}
          {incident.status === "ACKNOWLEDGED" && (
            <button
              onClick={() => onResolve(incident.id)}
              className="w-full py-2.5 rounded bg-[rgba(0,229,255,0.12)] text-[#00e5ff] hover:bg-[#00e5ff] hover:text-black border border-[#00e5ff44] font-bold transition-all flex items-center justify-center gap-1.5"
            >
              <Shield className="w-3.5 h-3.5" /> RESOLVE INCIDENT
            </button>
          )}
        </div>
      </div>
    </div>
  );
};

/* ═══════════════════════════════════════════════════════════════════
   INCIDENTS VIEW — Incident Feed & Timeline
   ═══════════════════════════════════════════════════════════════════ */
export const IncidentsView: React.FC = () => {
  const [incidents, setIncidents] = useState(DEMO_INCIDENTS);
  const [selectedIncident, setSelectedIncident] = useState<DemoIncident | null>(null);
  const [filterSeverity, setFilterSeverity] = useState<string>("all");

  const filtered = incidents.filter((inc) => {
    if (filterSeverity !== "all" && inc.severity !== filterSeverity) return false;
    return true;
  });

  const acknowledge = (id: string) => {
    setIncidents((prev) => prev.map((inc) => (inc.id === id ? { ...inc, status: "ACKNOWLEDGED" as const } : inc)));
    setSelectedIncident((prev) => (prev?.id === id ? { ...prev, status: "ACKNOWLEDGED" as const } : prev));
  };

  const resolve = (id: string) => {
    setIncidents((prev) => prev.map((inc) => (inc.id === id ? { ...inc, status: "RESOLVED" as const } : inc)));
    setSelectedIncident((prev) => (prev?.id === id ? { ...prev, status: "RESOLVED" as const } : prev));
  };

  return (
    <div className="space-y-4 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3 pb-2 border-b border-[var(--border-dim)]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded border border-[rgba(255,23,68,0.3)] bg-[rgba(255,23,68,0.06)] flex items-center justify-center">
            <AlertTriangle className="w-4 h-4 text-[#ff5252]" />
          </div>
          <div>
            <h2 className="font-condensed font-bold text-lg tracking-wide text-white uppercase">
              TACTICAL INCIDENT MANAGEMENT
            </h2>
            <p className="text-[10px] font-mono text-[#64748b]">
              REDUCING MULTI-DETECTION NOISE: 1 INCIDENT = 1 OPERATOR ALERT
            </p>
          </div>
        </div>

        {/* Severity Filters */}
        <div className="flex items-center gap-1 bg-[rgba(8,13,22,0.9)] p-1 rounded border border-[rgba(255,255,255,0.06)] font-mono text-[10px]">
          {["all", "critical", "restricted", "warning"].map((sev) => (
            <button
              key={sev}
              onClick={() => setFilterSeverity(sev)}
              className={`px-3 py-1 rounded uppercase font-bold transition-all ${
                filterSeverity === sev
                  ? "bg-[#00e5ff] text-black shadow-[0_0_8px_#00e5ff]"
                  : "text-[#64748b] hover:text-white"
              }`}
            >
              {sev}
            </button>
          ))}
        </div>
      </div>

      {/* Incident Cards Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
        {filtered.map((inc) => {
          const sc = getSeverityColor(inc.severity);
          return (
            <div
              key={inc.id}
              onClick={() => setSelectedIncident(inc)}
              className="p-4 rounded border border-[rgba(255,255,255,0.08)] bg-[rgba(8,13,22,0.95)] hover:border-[#00e5ff55] cursor-pointer transition-all shadow-md flex flex-col justify-between font-mono space-y-3"
            >
              <div>
                <div className="flex items-center justify-between text-[10px] mb-2">
                  <span
                    className="px-2 py-0.5 rounded font-bold uppercase text-[8px]"
                    style={{ backgroundColor: `${sc}18`, color: sc, border: `1px solid ${sc}40` }}
                  >
                    {inc.severity}
                  </span>
                  <span className="text-[#64748b]">{formatTimestamp(inc.firstSeen)}</span>
                </div>

                <h4 className="font-condensed font-bold text-base text-white uppercase tracking-wide">
                  {inc.description}
                </h4>

                <div className="mt-2 text-xs text-[#94a3b8] space-y-1">
                  <div>TARGET: <strong className="text-[#00e5ff]">GLOBAL-PERSON-042</strong></div>
                  <div>SECTOR: {inc.cameraId}</div>
                  <div>STATUS: <strong className="text-white">{inc.status}</strong></div>
                </div>
              </div>

              <div className="flex items-center justify-between pt-3 border-t border-[rgba(255,255,255,0.06)] text-xs">
                <span className="font-bold text-base" style={{ color: sc }}>
                  {inc.threatScore} <span className="text-[10px] text-[#64748b]">/ 100</span>
                </span>
                <span className="text-[#00e5ff] flex items-center gap-1 text-[11px] font-bold">
                  VIEW DOSSIER <ChevronRight className="w-3.5 h-3.5" />
                </span>
              </div>
            </div>
          );
        })}
      </div>

      {/* Selected Incident Drawer */}
      {selectedIncident && (
        <IncidentDetail
          incident={selectedIncident}
          onClose={() => setSelectedIncident(null)}
          onAcknowledge={acknowledge}
          onResolve={resolve}
        />
      )}
    </div>
  );
};
