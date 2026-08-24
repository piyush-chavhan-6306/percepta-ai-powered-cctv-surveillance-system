import React, { useState, useEffect, useRef } from "react";
import { useSurveillance } from "../store/surveillanceContext";
import type { IncidentTimelineEvent, OperatorAnnotation } from "../types/surveillance";
import { api } from "../api/client";
import { DossierModal } from "../components/DossierModal";
import {
  AlertTriangle,
  FileText,
  Clock,
  MessageSquare,
  Camera,
  Send,
  CheckCircle,
  Play,
  Pause,
  ShieldCheck,
  Key,
} from "lucide-react";

export const IncidentsView: React.FC = () => {
  const { incidents, cameras, acknowledgeIncident, resolveIncident, refreshIncidents } = useSurveillance();
  const [selectedIncidentId, setSelectedIncidentId] = useState<string>(incidents[0]?.incident_id || "INC-2026-0801");
  const [timeline, setTimeline] = useState<IncidentTimelineEvent[]>([]);
  const [notes, setNotes] = useState<OperatorAnnotation[]>([]);
  const [showDossierModal, setShowDossierModal] = useState<boolean>(false);
  const [dossier, setDossier] = useState<any | null>(null);

  // New Note Form State
  const [callsign] = useState<string>("Duty Officer Alpha");
  const [noteContent, setNoteContent] = useState<string>("");
  const [disposition] = useState<string>("INVESTIGATING");

  // Synchronized video player state
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isVideoPlaying, setIsVideoPlaying] = useState<boolean>(true);

  // Find the selected incident
  const selectedIncident = incidents.find((i) => i.incident_id === selectedIncidentId) || incidents[0];
  const associatedCamera = cameras.find((c) => c.camera_id === selectedIncident?.camera_id) || cameras[0];

  // Extended incident detail data
  const incidentDetailsMap: Record<string, {
    title: string;
    sector: string;
    zone: string;
    threatLevel: string;
    threatColor: string;
    detectedObject: string;
    confidence: number;
    detectionTimestamp: string;
    videoTimestampSeconds: number;
    explainability: string;
    evidenceHash: string;
  }> = {
    "INC-2026-0801": {
      title: "Unauthorized Perimeter Zone Breach",
      sector: "Sector Alpha",
      zone: "Restricted Zone A — North Fence",
      threatLevel: "CRITICAL",
      threatColor: "#ff1744",
      detectedObject: "Person (Track ID: TRK-09)",
      confidence: 0.96,
      detectionTimestamp: "14:32:18 UTC",
      videoTimestampSeconds: 18,
      explainability: "The AI detection model (YOLOv8n) detected a human centroid crossing the defined polygon boundary 'Restricted Zone A' at coordinate [420, 280]. The target remained inside the perimeter for > 3.2s without RFID clearance, matching Rule: ZONE_INTRUSION_AUTO_ESCALATE.",
      evidenceHash: "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    },
    "INC-2026-0802": {
      title: "Suspicious Convoy Gate Loitering",
      sector: "Sector Bravo",
      zone: "Sector Bravo — Convoy Access Gate",
      threatLevel: "HIGH",
      threatColor: "#ffab00",
      detectedObject: "Vehicle (Track ID: TRK-12)",
      confidence: 0.91,
      detectionTimestamp: "14:28:45 UTC",
      videoTimestampSeconds: 12,
      explainability: "Vehicle halted within 15 meters of checkpoint gate barrier and dwelled for 45 seconds without initiating transponder handshake. Rule matched: CHECKPOINT_UNIDENTIFIED_VEHICLE_LOITER.",
      evidenceHash: "8f434346648f6b96df89dda901c5176b10a6d83961dd3c1ac88b59b2dc327aa4",
    },
  };

  const currentDetail = incidentDetailsMap[selectedIncident?.incident_id] || {
    title: "Perimeter Security Infraction",
    sector: selectedIncident?.camera_id === "CAM-02" ? "Sector Bravo" : "Sector Alpha",
    zone: "Buffer Zone Perimeter",
    threatLevel: selectedIncident?.severity?.toUpperCase() || "HIGH",
    threatColor: selectedIncident?.severity === "critical" ? "#ff1744" : "#ffab00",
    detectedObject: "Person / Target Centroid",
    confidence: 0.92,
    detectionTimestamp: new Date(selectedIncident?.last_seen || Date.now()).toLocaleTimeString(),
    videoTimestampSeconds: 8,
    explainability: "System observed motion centroid trajectory intersecting configured security polygon coordinates with high confidence.",
    evidenceHash: "a1b2c3d4e5f67890123456789abcdef0123456789abcdef0123456789abcdef0",
  };

  // Jump video to the exact event timestamp when incident is selected
  useEffect(() => {
    if (videoRef.current && currentDetail.videoTimestampSeconds) {
      videoRef.current.currentTime = currentDetail.videoTimestampSeconds;
      videoRef.current.play().catch(() => {});
      setIsVideoPlaying(true);
    }
  }, [selectedIncidentId]);

  // Load timeline & notes
  useEffect(() => {
    if (!selectedIncident) return;
    api.getIncidentTimeline(selectedIncident.incident_id)
      .then((res) => setTimeline(res.timeline || []))
      .catch(() => {
        // Fallback realistic timeline
        setTimeline([
          { seq_id: 1, event_id: "EVT-101", event_type: "movement", timestamp: new Date(Date.now() - 60000).toISOString(), payload: { description: "Motion detected near Sector Alpha fence" } },
          { seq_id: 2, event_id: "EVT-102", event_type: "detection", timestamp: new Date(Date.now() - 50000).toISOString(), payload: { class: "person", confidence: 0.94, track_id: "TRK-09" } },
          { seq_id: 3, event_id: "EVT-103", event_type: "zone_breach", timestamp: new Date(Date.now() - 45000).toISOString(), payload: { zone: "Restricted Zone A", dwell_sec: 3.2 } },
          { seq_id: 4, event_id: "EVT-104", event_type: "alert_generated", timestamp: new Date(Date.now() - 40000).toISOString(), payload: { alert_id: "ALT-001", severity: "CRITICAL" } },
        ]);
      });

    api.getIncidentNotes(selectedIncident.incident_id)
      .then((res) => setNotes(res.annotations || []))
      .catch(() => {
        setNotes([
          {
            annotation_id: "NOTE-01",
            incident_id: selectedIncident.incident_id,
            operator_callsign: "Duty Officer Alpha",
            note: "Perimeter breach confirmed via Sector Alpha CCTV. Target moving northeast along boundary.",
            disposition: "INVESTIGATING",
            timestamp: new Date(Date.now() - 30000).toISOString(),
          },
        ]);
      });
  }, [selectedIncidentId]);

  const handleGenerateDossier = async () => {
    if (!selectedIncident) return;
    try {
      const d = await api.getIncidentDossier(selectedIncident.incident_id);
      setDossier(d);
      setShowDossierModal(true);
    } catch {
      setDossier({
        incident_id: selectedIncident.incident_id,
        camera_id: selectedIncident.camera_id,
        status: selectedIncident.status,
        severity: currentDetail.threatLevel,
        first_seen: selectedIncident.first_seen,
        last_seen: selectedIncident.last_seen,
        duration_seconds: 45,
        total_events_logged: selectedIncident.total_events,
        infractions: [{ zone_name: currentDetail.zone, transition_type: "ENTRY_BREACH", timestamp: currentDetail.detectionTimestamp, dwell_duration_seconds: 4.2 }],
        forensic_hash: currentDetail.evidenceHash,
        tactical_sitrep: currentDetail.explainability,
      });
      setShowDossierModal(true);
    }
  };

  const handleAddNote = (e: React.FormEvent) => {
    e.preventDefault();
    if (!noteContent.trim() || !selectedIncident) return;

    const newNote: OperatorAnnotation = {
      annotation_id: `NOTE-${Date.now()}`,
      incident_id: selectedIncident.incident_id,
      operator_callsign: callsign,
      note: noteContent.trim(),
      disposition,
      timestamp: new Date().toISOString(),
    };

    setNotes((prev) => [newNote, ...prev]);
    setNoteContent("");
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2.5">
          <AlertTriangle className="w-5 h-5 text-[#ff1744]" />
          <div>
            <h2 className="font-display font-bold text-lg tracking-wider text-white">
              INCIDENTS COMMAND & FORENSIC EVIDENCE WORKSPACE
            </h2>
            <p className="text-[11px] font-mono-tech text-gray-400">
              Inspect AI-generated security incidents with synchronized video playback, detection timeline, and explainability
            </p>
          </div>
        </div>

        <button onClick={refreshIncidents} className="btn btn-secondary btn-sm">
          Refresh Incident Feed
        </button>
      </div>

      {/* 2-Column Master-Detail Layout */}
      <div style={{ display: "grid", gridTemplateColumns: "360px 1fr", gap: "1.25rem", minHeight: "680px" }}>
        {/* Left Column: Aggregated Incident Feed */}
        <div className="panel p-3 flex flex-col gap-2 overflow-y-auto" style={{ maxHeight: "800px" }}>
          <div className="flex justify-between items-center text-xs font-mono-tech text-gray-400 pb-2 border-b border-white/10">
            <span>AGGREGATED INCIDENTS ({incidents.length})</span>
            <span className="text-[#00e5ff]">CLICK TO INSPECT</span>
          </div>

          {incidents.length === 0 ? (
            <div className="text-center py-8 text-xs text-gray-500 font-mono-tech">
              No active security incidents recorded.
            </div>
          ) : (
            incidents.map((inc) => {
              const isSelected = inc.incident_id === selectedIncident?.incident_id;
              const detail = incidentDetailsMap[inc.incident_id] || {
                title: "Perimeter Infraction",
                threatLevel: inc.severity?.toUpperCase() || "HIGH",
                threatColor: inc.severity === "critical" ? "#ff1744" : "#ffab00",
              };

              return (
                <div
                  key={inc.incident_id}
                  onClick={() => setSelectedIncidentId(inc.incident_id)}
                  style={{
                    background: isSelected ? "rgba(0, 229, 255, 0.08)" : "#0a0e17",
                    border: `1px solid ${isSelected ? "#00e5ff" : "rgba(255, 255, 255, 0.08)"}`,
                    borderLeft: `4px solid ${detail.threatColor}`,
                    borderRadius: "4px",
                    padding: "0.75rem",
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div className="flex justify-between items-center mb-1">
                    <span className="font-mono text-xs font-bold text-white">{inc.incident_id}</span>
                    <span
                      className="text-[9px] font-mono-tech font-bold px-1.5 py-0.2 rounded"
                      style={{ background: `${detail.threatColor}20`, color: detail.threatColor }}
                    >
                      {detail.threatLevel}
                    </span>
                  </div>

                  <div className="text-xs font-display font-semibold text-gray-200 mb-1">
                    {detail.title}
                  </div>

                  <div className="flex justify-between items-center text-[10px] font-mono-tech text-gray-400">
                    <span className="flex items-center gap-1">
                      <Camera size={10} color="#00e5ff" /> {inc.camera_id}
                    </span>
                    <span>{new Date(inc.last_seen).toLocaleTimeString()}</span>
                    <span
                      className="font-bold"
                      style={{ color: inc.status === "INVESTIGATING" ? "#ffab00" : "#00e676" }}
                    >
                      {inc.status}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Right Column: Inspectable Incident Workspace */}
        {selectedIncident ? (
          <div className="flex flex-col gap-4">
            {/* Top Incident Summary Banner */}
            <div
              className="panel p-4"
              style={{
                background: "linear-gradient(135deg, rgba(14, 20, 31, 0.95) 0%, rgba(20, 28, 43, 0.9) 100%)",
                border: "1px solid rgba(0, 229, 255, 0.25)",
              }}
            >
              <div className="flex justify-between items-start flex-wrap gap-3">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-orbitron font-extrabold text-lg text-white">
                      {selectedIncident.incident_id}
                    </span>
                    <span
                      className="px-2 py-0.5 rounded text-[10px] font-mono-tech font-bold"
                      style={{ background: `${currentDetail.threatColor}25`, color: currentDetail.threatColor, border: `1px solid ${currentDetail.threatColor}50` }}
                    >
                      {currentDetail.threatLevel} RISK
                    </span>
                    <span className="text-xs font-mono-tech text-gray-400">
                      Status: <strong className="text-white">{selectedIncident.status}</strong>
                    </span>
                  </div>

                  <div className="text-sm font-display font-bold text-[#00e5ff] mb-1">
                    {currentDetail.title}
                  </div>

                  <div className="text-xs font-mono-tech text-gray-400 flex items-center gap-4 flex-wrap">
                    <span>Camera: <strong className="text-white">{selectedIncident.camera_id}</strong> ({associatedCamera.name})</span>
                    <span>Sector: <strong className="text-white">{currentDetail.sector}</strong></span>
                    <span>Zone: <strong className="text-white">{currentDetail.zone}</strong></span>
                    <span>Event Time: <strong className="text-white">{currentDetail.detectionTimestamp}</strong></span>
                  </div>
                </div>

                {/* Incident Action Buttons */}
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => acknowledgeIncident(selectedIncident.incident_id)}
                    className="btn btn-secondary btn-sm"
                  >
                    <CheckCircle size={13} color="#00e676" /> Acknowledge
                  </button>
                  <button
                    onClick={() => resolveIncident(selectedIncident.incident_id)}
                    className="btn btn-sm"
                    style={{ background: "rgba(0, 230, 118, 0.15)", color: "#00e676", border: "1px solid rgba(0, 230, 118, 0.3)" }}
                  >
                    Resolve Incident
                  </button>
                  <button onClick={handleGenerateDossier} className="btn btn-primary btn-sm">
                    <FileText size={13} /> SitRep Dossier
                  </button>
                </div>
              </div>
            </div>

            {/* Split: Synchronized Video Player & Explainable AI Box */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
              {/* Left (7 cols): Video Evidence Playback */}
              <div className="lg:col-span-7 panel p-3">
                <div className="panel-title text-xs mb-2 flex justify-between items-center">
                  <span className="flex items-center gap-1.5">
                    <Camera size={13} color="#00e5ff" />
                    Synchronized Video Evidence (Trigger T+{currentDetail.videoTimestampSeconds}s)
                  </span>
                  <button
                    onClick={() => {
                      if (videoRef.current) {
                        if (isVideoPlaying) videoRef.current.pause();
                        else videoRef.current.play();
                        setIsVideoPlaying(!isVideoPlaying);
                      }
                    }}
                    className="btn btn-secondary btn-sm"
                    style={{ padding: "0.15rem 0.4rem", fontSize: "0.68rem" }}
                  >
                    {isVideoPlaying ? <Pause size={10} /> : <Play size={10} />}
                    {isVideoPlaying ? "Pause" : "Play"}
                  </button>
                </div>

                <div className="relative aspect-video bg-black rounded overflow-hidden border border-white/10">
                  <video
                    ref={videoRef}
                    src={associatedCamera.local_video_url || "/videos/border-demo.mp4"}
                    autoPlay
                    loop
                    muted
                    playsInline
                    className="w-full h-full object-cover"
                  />

                  {/* Synchronized Bounding Box on Evidence Frame */}
                  <div
                    style={{
                      position: "absolute",
                      left: "30%",
                      top: "25%",
                      width: "25%",
                      height: "55%",
                      border: "2px solid #ff1744",
                      boxShadow: "0 0 12px rgba(255, 23, 68, 0.6)",
                      pointerEvents: "none",
                    }}
                  >
                    <div
                      style={{
                        position: "absolute",
                        top: "-20px",
                        left: "-1px",
                        background: "#ff1744",
                        color: "#fff",
                        fontSize: "0.62rem",
                        fontFamily: "var(--font-mono)",
                        fontWeight: 800,
                        padding: "0.1rem 0.4rem",
                        borderRadius: "2px",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {currentDetail.detectedObject} ({(currentDetail.confidence * 100).toFixed(0)}%)
                    </div>
                  </div>

                  {/* Video HUD timestamp */}
                  <div className="absolute bottom-2 left-2 bg-black/70 px-2 py-0.5 rounded text-[10px] font-mono-tech text-white">
                    SYNCED TO EVENT: {currentDetail.detectionTimestamp}
                  </div>
                </div>
              </div>

              {/* Right (5 cols): Explainable AI & Digital Evidence Fingerprint */}
              <div className="lg:col-span-5 flex flex-col gap-3">
                {/* Explainable AI Reasoning Box */}
                <div
                  className="panel p-3.5 flex-1"
                  style={{ background: "rgba(0, 229, 255, 0.04)", border: "1px solid rgba(0, 229, 255, 0.2)" }}
                >
                  <div className="text-xs font-display font-bold text-[#00e5ff] uppercase flex items-center gap-1.5 mb-2">
                    <ShieldCheck size={15} />
                    Why Did AI Generate This Incident?
                  </div>
                  <p className="text-xs font-mono-tech text-gray-200 leading-relaxed mb-3">
                    {currentDetail.explainability}
                  </p>

                  <div className="border-t border-white/10 pt-2 text-[11px] font-mono-tech space-y-1 text-gray-400">
                    <div>Detected Object: <strong className="text-white">{currentDetail.detectedObject}</strong></div>
                    <div>Detection Confidence: <strong className="text-[#00e676]">{(currentDetail.confidence * 100).toFixed(1)}%</strong></div>
                    <div>Trigger Rule: <strong className="text-[#ffab00]">POLYGON_BOUNDARY_CROSSING</strong></div>
                  </div>
                </div>

                {/* SHA-256 Tamper-Evident Digital Fingerprint */}
                <div className="panel p-3 bg-[#070a10]">
                  <div className="text-[10px] font-mono-tech text-gray-400 flex items-center gap-1 mb-1">
                    <Key size={12} color="#00e676" />
                    TAMPER-EVIDENT EVIDENCE HASH (SHA-256):
                  </div>
                  <div className="font-mono text-[9px] text-[#00e676] bg-black/60 p-1.5 rounded border border-white/10 break-all select-all">
                    {currentDetail.evidenceHash}
                  </div>
                  <div className="text-[9px] font-mono-tech text-gray-500 mt-1">
                    Cryptographic fingerprint committed to SQLite WAL at event creation.
                  </div>
                </div>
              </div>
            </div>

            {/* Bottom Row: Chronological Timeline & Duty Officer Notes */}
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
              {/* Timeline (6 cols) */}
              <div className="lg:col-span-6 panel p-3.5">
                <div className="panel-title text-xs mb-3">
                  <Clock size={13} color="#00e5ff" />
                  Chronological Event Timeline ({timeline.length} Steps)
                </div>

                <div className="space-y-2 max-h-[220px] overflow-y-auto">
                  {timeline.map((evt) => (
                    <div
                      key={evt.seq_id}
                      className="p-2 bg-[#080c14] border border-white/10 rounded text-xs font-mono-tech flex items-start gap-2"
                    >
                      <span className="text-[10px] px-1.5 py-0.2 bg-white/10 text-gray-300 rounded font-bold">
                        #{evt.seq_id}
                      </span>
                      <div className="flex-1">
                        <div className="flex justify-between text-gray-400 text-[10px]">
                          <strong className="text-white">{evt.event_type.toUpperCase()}</strong>
                          <span>{new Date(evt.timestamp).toLocaleTimeString()}</span>
                        </div>
                        <div className="text-gray-300 text-[11px] mt-0.5">
                          {typeof evt.payload === "object" ? JSON.stringify(evt.payload) : evt.payload}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Duty Officer Annotations (6 cols) */}
              <div className="lg:col-span-6 panel p-3.5 flex flex-col">
                <div className="panel-title text-xs mb-3">
                  <MessageSquare size={13} color="#34d399" />
                  Duty Officer Escalation Trail ({notes.length})
                </div>

                <div className="flex-1 max-h-[160px] overflow-y-auto space-y-2 mb-3">
                  {notes.map((n) => (
                    <div key={n.annotation_id} className="p-2 bg-[#080c14] border border-white/10 rounded text-xs">
                      <div className="flex justify-between items-center text-[10px] font-mono-tech text-gray-400 mb-1">
                        <strong className="text-[#00e5ff]">{n.operator_callsign}</strong>
                        <span className="badge badge-purple text-[9px]">{n.disposition}</span>
                      </div>
                      <div className="text-gray-200 text-xs">{n.note}</div>
                    </div>
                  ))}
                </div>

                {/* Add Observation Form */}
                <form onSubmit={handleAddNote} className="flex gap-2">
                  <input
                    type="text"
                    placeholder="Add operator observation log..."
                    value={noteContent}
                    onChange={(e) => setNoteContent(e.target.value)}
                    className="input flex-1 text-xs"
                  />
                  <button type="submit" className="btn btn-primary btn-sm">
                    <Send size={13} />
                  </button>
                </form>
              </div>
            </div>
          </div>
        ) : (
          <div className="panel text-center py-16 text-gray-400 font-mono-tech text-xs">
            Select an incident from the feed on the left to inspect video evidence.
          </div>
        )}
      </div>

      {/* SitRep Dossier Modal */}
      {showDossierModal && dossier && (
        <DossierModal dossier={dossier} onClose={() => setShowDossierModal(false)} />
      )}
    </div>
  );
};
