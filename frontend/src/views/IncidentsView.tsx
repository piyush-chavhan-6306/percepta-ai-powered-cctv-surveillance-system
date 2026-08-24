import React, { useState, useEffect } from "react";
import { useSurveillance } from "../store/surveillanceContext";
import type { IncidentTimelineEvent, OperatorAnnotation, IncidentDossier } from "../types/surveillance";
import { api } from "../api/client";
import {
  AlertTriangle,
  Clock,
  MessageSquare,
  Send,
  RefreshCw,
  Download,
  Image as ImageIcon,
} from "lucide-react";

export const IncidentsView: React.FC = () => {
  const { incidents, refreshIncidents, refreshAll } = useSurveillance();
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(
    incidents[0]?.incident_id || null
  );
  const [timeline, setTimeline] = useState<IncidentTimelineEvent[]>([]);
  const [notes, setNotes] = useState<OperatorAnnotation[]>([]);
  const [dossier, setDossier] = useState<IncidentDossier | null>(null);
  const [snapshots, setSnapshots] = useState<any[]>([]);
  const [noteContent, setNoteContent] = useState<string>("");
  const [callsign, setCallsign] = useState<string>("Duty Officer Alpha");
  const [isSubmittingNote, setIsSubmittingNote] = useState<boolean>(false);

  useEffect(() => {
    if (incidents.length > 0 && !selectedIncidentId) {
      setSelectedIncidentId(incidents[0].incident_id);
    }
  }, [incidents, selectedIncidentId]);

  useEffect(() => {
    if (!selectedIncidentId) return;

    Promise.allSettled([
      api.getIncidentTimeline(selectedIncidentId),
      api.getIncidentDossier(selectedIncidentId),
      api.getIncidentNotes(selectedIncidentId),
      api.getSnapshots(selectedIncidentId),
    ])
      .then(([timeRes, dosRes, noteRes, snapRes]) => {
        if (timeRes.status === "fulfilled" && timeRes.value?.timeline) {
          setTimeline(timeRes.value.timeline);
        } else {
          setTimeline([]);
        }

        if (dosRes.status === "fulfilled" && dosRes.value) {
          setDossier(dosRes.value);
        } else {
          setDossier(null);
        }

        if (noteRes.status === "fulfilled" && noteRes.value?.annotations) {
          setNotes(noteRes.value.annotations);
        } else {
          setNotes([]);
        }

        if (snapRes.status === "fulfilled" && snapRes.value?.snapshots) {
          setSnapshots(snapRes.value.snapshots);
        } else {
          setSnapshots([]);
        }
      });
  }, [selectedIncidentId]);

  const handleAddNote = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedIncidentId || !noteContent.trim()) return;

    setIsSubmittingNote(true);
    try {
      const added = await api.addIncidentNote(selectedIncidentId, {
        operator_callsign: callsign,
        note: noteContent.trim(),
        disposition: "INVESTIGATING",
      });
      setNotes((prev) => [added, ...prev]);
      setNoteContent("");
    } catch (err: any) {
      alert(`Failed to add note: ${err.message}`);
    } finally {
      setIsSubmittingNote(false);
    }
  };

  const selectedIncident = incidents.find((i) => i.incident_id === selectedIncidentId) || incidents[0];

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="flex items-center justify-between flex-wrap gap-3 bg-[#0a0f18] border border-white/10 p-3 rounded-sm">
        <div className="flex items-center gap-2.5">
          <AlertTriangle className="w-5 h-5 text-[#ff1744]" />
          <div>
            <h3 className="font-display font-bold text-base tracking-wider text-white">
              INCIDENT COMMAND & SITREP DOSSIER WORKSPACE
            </h3>
            <p className="font-mono-tech text-[11px] text-gray-400">
              Correlated security event timelines, cryptographic hash audit, and evidence logging
            </p>
          </div>
        </div>

        <button
          onClick={() => {
            refreshIncidents();
            refreshAll();
          }}
          className="p-1.5 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded transition-colors"
          title="Refresh Incidents"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Main Grid Layout */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column (4 cols): Incidents Queue */}
        <div className="col-span-12 lg:col-span-4 bg-[#090d14] border border-white/10 rounded-sm overflow-hidden flex flex-col min-h-[600px]">
          <div className="px-4 py-3 bg-[#0e141f] border-b border-white/10 flex items-center justify-between">
            <h4 className="font-display font-bold text-sm text-white">
              RECORDED INCIDENTS ({incidents.length})
            </h4>
            <span className="text-[10px] font-mono-tech text-gray-400">
              SQLITE PERSISTED
            </span>
          </div>

          <div className="flex-1 p-3 overflow-y-auto space-y-2.5 max-h-[680px]">
            {incidents.length > 0 ? (
              incidents.map((inc) => {
                const isSelected = inc.incident_id === selectedIncidentId;
                const isCritical = inc.severity?.toUpperCase() === "CRITICAL";

                return (
                  <div
                    key={inc.incident_id}
                    onClick={() => setSelectedIncidentId(inc.incident_id)}
                    className={`p-3.5 rounded border transition-all cursor-pointer flex flex-col gap-1.5 ${
                      isSelected
                        ? "bg-[#121c2c] border-[#00e5ff] shadow-[0_0_12px_rgba(0,229,255,0.2)]"
                        : "bg-[#060a12] border-white/10 hover:border-white/20"
                    }`}
                  >
                    <div className="flex items-center justify-between text-[11px] font-mono-tech">
                      <span className="text-[#00e5ff] font-bold">
                        {inc.incident_id}
                      </span>
                      <span
                        className={`px-1.5 py-0.2 rounded text-[9px] font-bold uppercase ${
                          isCritical
                            ? "bg-red-500/20 text-red-400 border border-red-500/30"
                            : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                        }`}
                      >
                        {inc.severity}
                      </span>
                    </div>

                    <div className="flex items-center justify-between text-xs text-gray-300 font-sans">
                      <span>Camera: <strong className="text-white">{inc.camera_id}</strong></span>
                      <span className="text-gray-400 font-mono-tech text-[10px]">
                        {inc.total_events} events
                      </span>
                    </div>

                    <div className="text-[10px] font-mono-tech text-gray-500 flex items-center justify-between pt-1 border-t border-white/5">
                      <span>{new Date(inc.first_seen).toLocaleTimeString()}</span>
                      <span className="text-gray-400 uppercase">{inc.status}</span>
                    </div>
                  </div>
                );
              })
            ) : (
              <div className="p-8 text-center text-gray-500 font-mono-tech text-xs">
                No security incidents logged yet. Triggering a zone breach will log an incident here.
              </div>
            )}
          </div>
        </div>

        {/* Right Column (8 cols): Incident Details, Timeline, Dossier & Notes */}
        <div className="col-span-12 lg:col-span-8 space-y-4">
          {selectedIncident ? (
            <>
              {/* Incident Header Card */}
              <div className="bg-[#090d14] border border-white/10 p-4 rounded-sm space-y-3">
                <div className="flex items-center justify-between flex-wrap gap-2 border-b border-white/10 pb-3">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-orbitron font-extrabold text-lg text-white">
                        {selectedIncident.incident_id}
                      </span>
                      <span className="font-mono-tech text-xs px-2 py-0.5 bg-red-500/20 text-red-400 border border-red-500/30 rounded font-bold uppercase">
                        {selectedIncident.severity} SEVERITY
                      </span>
                    </div>
                    <p className="font-mono-tech text-xs text-gray-400 mt-1">
                      Camera: <strong className="text-white">{selectedIncident.camera_id}</strong> • First Seen: {new Date(selectedIncident.first_seen).toLocaleString()}
                    </p>
                  </div>

                  {dossier && (
                    <a
                      href={api.getExportUrl("json", selectedIncident.camera_id)}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-[#00e5ff] border border-[#00e5ff]/30 rounded text-xs font-display font-bold flex items-center gap-1.5 transition-colors"
                    >
                      <Download className="w-3.5 h-3.5" />
                      <span>EXPORT AUDIT JSON</span>
                    </a>
                  )}
                </div>

                {/* Dossier Summary Box */}
                {dossier && (
                  <div className="grid grid-cols-3 gap-3 font-mono-tech text-xs">
                    <div className="bg-[#060a12] p-2.5 rounded border border-white/5">
                      <span className="text-gray-500 text-[10px] block">TOTAL EVENTS</span>
                      <span className="text-white font-bold text-sm">{dossier.total_events_logged}</span>
                    </div>
                    <div className="bg-[#060a12] p-2.5 rounded border border-white/5">
                      <span className="text-gray-500 text-[10px] block">INFRACTIONS</span>
                      <span className="text-[#00e5ff] font-bold text-sm">{dossier.infractions?.length || 0}</span>
                    </div>
                    <div className="bg-[#060a12] p-2.5 rounded border border-white/5">
                      <span className="text-gray-500 text-[10px] block">DURATION</span>
                      <span className="text-[#ffab00] font-bold text-sm">{dossier.duration_seconds.toFixed(1)}s</span>
                    </div>
                  </div>
                )}
              </div>

              {/* Snapshots / Evidence Section */}
              {snapshots.length > 0 && (
                <div className="bg-[#090d14] border border-white/10 p-4 rounded-sm space-y-2.5">
                  <div className="flex items-center gap-2 text-xs font-display font-bold text-white border-b border-white/10 pb-2">
                    <ImageIcon className="w-4 h-4 text-[#00e5ff]" />
                    <span>CAPTURED EVIDENCE SNAPSHOTS ({snapshots.length})</span>
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {snapshots.map((snap) => (
                      <div key={snap.snapshot_id} className="bg-[#060a12] border border-white/10 rounded p-2 space-y-1.5">
                        <img
                          src={api.getSnapshotFileUrl(snap.file_path)}
                          alt="Incident Snapshot"
                          className="w-full h-32 object-cover rounded border border-white/5"
                        />
                        <div className="text-[10px] font-mono-tech text-gray-400">
                          <div>Track ID: <strong>TRK-{snap.track_id}</strong></div>
                          <div>{new Date(snap.timestamp).toLocaleTimeString()}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Timeline Section */}
              <div className="bg-[#090d14] border border-white/10 p-4 rounded-sm space-y-3">
                <div className="flex items-center gap-2 text-xs font-display font-bold text-white border-b border-white/10 pb-2">
                  <Clock className="w-4 h-4 text-[#ffab00]" />
                  <span>CHRONOLOGICAL EVENT TIMELINE ({timeline.length})</span>
                </div>

                <div className="space-y-2 max-h-[300px] overflow-y-auto">
                  {timeline.length > 0 ? (
                    timeline.map((evt, idx) => (
                      <div
                        key={idx}
                        className="p-2.5 bg-[#060a12] border border-white/5 rounded flex items-start justify-between gap-3 text-xs"
                      >
                        <div className="space-y-0.5">
                          <div className="flex items-center gap-2">
                            <span className="font-mono-tech text-[10px] px-1.5 py-0.2 bg-white/5 border border-white/10 rounded text-gray-300 uppercase font-bold">
                              {evt.event_type}
                            </span>
                            <span className="font-bold text-white">
                              Track TRK-{evt.payload?.track_id || evt.event_id}
                            </span>
                          </div>
                          <p className="text-gray-300 font-sans text-xs">
                            {evt.payload?.message || JSON.stringify(evt.payload)}
                          </p>
                        </div>

                        <span className="font-mono-tech text-[10px] text-gray-500 whitespace-nowrap">
                          {new Date(evt.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                    ))
                  ) : (
                    <div className="p-4 text-center text-gray-500 font-mono-tech text-xs">
                      No discrete timeline events recorded for this incident ID.
                    </div>
                  )}
                </div>
              </div>

              {/* Operator Notes & Annotations Section */}
              <div className="bg-[#090d14] border border-white/10 p-4 rounded-sm space-y-3">
                <div className="flex items-center gap-2 text-xs font-display font-bold text-white border-b border-white/10 pb-2">
                  <MessageSquare className="w-4 h-4 text-[#00e5ff]" />
                  <span>DUTY OPERATOR LOG & SITREP ANNOTATIONS</span>
                </div>

                {/* Add Note Form */}
                <form onSubmit={handleAddNote} className="space-y-2">
                  <div className="flex items-center gap-2">
                    <input
                      type="text"
                      value={callsign}
                      onChange={(e) => setCallsign(e.target.value)}
                      placeholder="Operator Callsign"
                      className="bg-[#060a12] border border-white/10 rounded px-2.5 py-1.5 text-xs text-white font-mono-tech w-48 focus:outline-none focus:border-[#00e5ff]"
                    />
                  </div>

                  <div className="flex gap-2">
                    <input
                      type="text"
                      required
                      value={noteContent}
                      onChange={(e) => setNoteContent(e.target.value)}
                      placeholder="Enter tactical observation / SITREP disposition note..."
                      className="flex-1 bg-[#060a12] border border-white/10 rounded px-3 py-2 text-xs text-white font-sans focus:outline-none focus:border-[#00e5ff]"
                    />
                    <button
                      type="submit"
                      disabled={isSubmittingNote}
                      className="px-4 py-2 bg-[#00e5ff] hover:bg-[#00cce6] text-black font-display font-bold text-xs rounded flex items-center gap-1.5 transition-colors"
                    >
                      <Send className="w-3.5 h-3.5" />
                      <span>LOG NOTE</span>
                    </button>
                  </div>
                </form>

                {/* Existing Notes List */}
                <div className="space-y-2 max-h-[200px] overflow-y-auto pt-2">
                  {notes.map((note, idx) => (
                    <div
                      key={idx}
                      className="p-2.5 bg-[#060a12] border border-white/5 rounded text-xs space-y-1"
                    >
                      <div className="flex items-center justify-between font-mono-tech text-[10px]">
                        <span className="text-[#00e5ff] font-bold">
                          {note.operator_callsign}
                        </span>
                        <span className="text-gray-500">
                          {new Date(note.timestamp).toLocaleTimeString()}
                        </span>
                      </div>
                      <p className="text-gray-200 font-sans">{note.note}</p>
                    </div>
                  ))}
                </div>
              </div>
            </>
          ) : (
            <div className="p-12 bg-[#090d14] border border-white/10 rounded text-center text-gray-500 font-mono-tech text-xs">
              Select an incident from the left queue to view details.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
