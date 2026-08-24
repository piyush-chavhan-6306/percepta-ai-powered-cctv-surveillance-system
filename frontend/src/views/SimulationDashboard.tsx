/**
 * SimulationDashboard — Functional MVP Demo
 *
 * Full pipeline:  MP4 video → Simulation Engine → Workflow Engine → Alerts → Dashboard
 *
 * The simulation engine polls video.currentTime every 100 ms and fires
 * configured scenario events at their timestamps.  Every event passes
 * through the workflow rule engine, which generates alerts and incidents.
 *
 * Source abstraction: replace DemoVideoSource with a LiveCameraSource
 * (RTSP/WebRTC) without changing the workflow engine or this dashboard.
 */
import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  Shield,
  AlertTriangle,
  Eye,
  Play,
  Pause,
  RotateCcw,
  Activity,
  Camera,
  Clock,
  CheckCircle,
  Zap,
  Radio,
} from "lucide-react";
import type { SurveillanceEvent, SurveillanceAlert, Incident } from "../lib/events/eventTypes";
import {
  DEMO_SCENARIO,
  DEMO_CAMERA_ID,
  DEMO_LOCATION,
  DEMO_VIDEO_PATH,
} from "../lib/simulation/demoScenario";
import { evaluateEvent, resetCounters } from "../lib/workflow/workflowEngine";

// ─── Types ────────────────────────────────────────────────────────────────────

type SimStatus = "IDLE" | "RUNNING" | "PAUSED" | "ENDED";

// ─── Helpers ─────────────────────────────────────────────────────────────────

function fmtTime(s: number): string {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

function alertBg(sev: SurveillanceAlert["severity"]): string {
  if (sev === "CRITICAL") return "rgba(255,23,68,0.12)";
  if (sev === "WARNING")  return "rgba(255,171,0,0.10)";
  return "rgba(0,229,255,0.08)";
}
function alertBorder(sev: SurveillanceAlert["severity"]): string {
  if (sev === "CRITICAL") return "rgba(255,23,68,0.45)";
  if (sev === "WARNING")  return "rgba(255,171,0,0.4)";
  return "rgba(0,229,255,0.3)";
}
function alertColor(sev: SurveillanceAlert["severity"]): string {
  if (sev === "CRITICAL") return "#ff1744";
  if (sev === "WARNING")  return "#ffab00";
  return "#00e5ff";
}
function evtIcon(type: SurveillanceEvent["type"]): string {
  switch (type) {
    case "ZONE_INTRUSION":    return "🚨";
    case "PERSON_DETECTED":   return "👤";
    case "VEHICLE_DETECTED":  return "🚗";
    case "MOVEMENT_DETECTED": return "📡";
  }
}
function evtLabel(type: SurveillanceEvent["type"]): string {
  switch (type) {
    case "ZONE_INTRUSION":    return "ZONE INTRUSION";
    case "PERSON_DETECTED":   return "PERSON DETECTED";
    case "VEHICLE_DETECTED":  return "VEHICLE DETECTED";
    case "MOVEMENT_DETECTED": return "MOVEMENT DETECTED";
  }
}
function evtBorderColor(type: SurveillanceEvent["type"]): string {
  switch (type) {
    case "ZONE_INTRUSION":    return "#ff1744";
    case "PERSON_DETECTED":   return "#ffab00";
    case "VEHICLE_DETECTED":  return "#ffab00";
    case "MOVEMENT_DETECTED": return "#334155";
  }
}

const S: React.CSSProperties = {};  // placeholder to satisfy type-checker on empty styles

// ─── Main Component ───────────────────────────────────────────────────────────

export function SimulationDashboard() {
  // Video + engine refs (mutations do NOT trigger re-renders)
  const videoRef      = useRef<HTMLVideoElement>(null);
  const firedRef      = useRef<Set<number>>(new Set());
  const evtCountRef   = useRef(0);

  // UI state
  const [status,           setStatus]           = useState<SimStatus>("IDLE");
  const [events,           setEvents]           = useState<SurveillanceEvent[]>([]);
  const [alerts,           setAlerts]           = useState<SurveillanceAlert[]>([]);
  const [incidents,        setIncidents]        = useState<Incident[]>([]);
  const [currentDetection, setCurrentDetection] = useState<SurveillanceEvent | null>(null);
  const [videoTime,        setVideoTime]        = useState(0);
  const [videoDuration,    setVideoDuration]    = useState(0);
  const [videoError,       setVideoError]       = useState(false);
  const [firedIndices,     setFiredIndices]     = useState<number[]>([]);
  const [workflowTrace,    setWorkflowTrace]    = useState<string | null>(null);

  // ── Simulation engine ─────────────────────────────────────────────────────
  useEffect(() => {
    if (status !== "RUNNING") return;

    const id = setInterval(() => {
      const video = videoRef.current;
      if (!video) return;

      const t = video.currentTime;
      setVideoTime(t);

      DEMO_SCENARIO.forEach((scenEvt, i) => {
        if (t >= scenEvt.time && !firedRef.current.has(i)) {
          firedRef.current.add(i);
          setFiredIndices((prev) => [...prev, i]);

          evtCountRef.current += 1;
          const event: SurveillanceEvent = {
            id:          `EVT-${String(evtCountRef.current).padStart(4, "0")}`,
            cameraId:    DEMO_CAMERA_ID,
            type:        scenEvt.type,
            description: scenEvt.description,
            timestamp:   new Date().toISOString(),
            videoTime:   t,
            confidence:  scenEvt.confidence,
            status:      "NEW",
            source:      "DEMO",
          };

          const { alert, incident, trace } = evaluateEvent(event);

          setEvents((prev) => [event, ...prev]);
          setCurrentDetection(event);

          if (alert) {
            setAlerts((prev) => [alert, ...prev]);
            setWorkflowTrace(trace);
            setTimeout(() => setWorkflowTrace(null), 5000);
          }
          if (incident) {
            setIncidents((prev) => [incident, ...prev]);
          }
        }
      });

      if (video.ended) setStatus("ENDED");
    }, 100);          // poll every 100 ms — plenty for demo precision

    return () => clearInterval(id);
  }, [status]);       // re-runs only when status changes

  // ── Controls ──────────────────────────────────────────────────────────────
  const handleStart = useCallback(() => {
    videoRef.current?.play().catch(() => {});
    setStatus("RUNNING");
  }, []);

  const handlePause = useCallback(() => {
    videoRef.current?.pause();
    setStatus("PAUSED");
  }, []);

  const handleRestart = useCallback(() => {
    const video = videoRef.current;
    if (video) { video.currentTime = 0; video.pause(); }
    firedRef.current  = new Set();
    evtCountRef.current = 0;
    resetCounters();
    setStatus("IDLE");
    setEvents([]);
    setAlerts([]);
    setIncidents([]);
    setCurrentDetection(null);
    setVideoTime(0);
    setFiredIndices([]);
    setWorkflowTrace(null);
  }, []);

  const handleAck = useCallback((alertId: string) => {
    setAlerts((prev) =>
      prev.map((a) => a.id === alertId ? { ...a, status: "ACKNOWLEDGED" } : a)
    );
  }, []);

  // ── Derived ───────────────────────────────────────────────────────────────
  const progress      = videoDuration > 0 ? (videoTime / videoDuration) * 100 : 0;
  const newAlertCount = alerts.filter((a) => a.status === "NEW").length;
  const statusColor   = status === "RUNNING" ? "#00e676"
                      : status === "PAUSED"  ? "#ffab00"
                      : status === "ENDED"   ? "#475569"
                      : "#334155";

  // ── Render ────────────────────────────────────────────────────────────────

  // Shared style tokens
  const panel: React.CSSProperties = {
    background: "#0e141f",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 6,
    padding: "0.85rem",
  };
  const sectionLabel: React.CSSProperties = {
    fontSize: "0.62rem",
    letterSpacing: "0.12em",
    color: "#475569",
    marginBottom: "0.65rem",
    display: "flex",
    alignItems: "center",
    gap: "0.35rem",
    textTransform: "uppercase",
  };
  void S; // suppress unused variable

  return (
    <div style={{ background: "#05070a", minHeight: "calc(100vh - 96px)", padding: "1rem", fontFamily: "var(--font-mono, 'JetBrains Mono', monospace)" }}>

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        borderBottom: "1px solid rgba(255,255,255,0.08)",
        paddingBottom: "0.75rem", marginBottom: "1rem",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "0.65rem" }}>
          <Shield size={18} color="#00e5ff" />
          <span style={{ fontSize: "1rem", fontWeight: 700, letterSpacing: "0.08em", color: "#fff" }}>
            BORDER WATCH — OPERATOR CONSOLE
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "1rem", fontSize: "0.68rem" }}>
          <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
            <Radio size={12} color="#00e676" />
            <span style={{ color: "#00e676", letterSpacing: "0.08em" }}>SYSTEM ONLINE</span>
          </span>

          <span style={{
            background: "rgba(255,171,0,0.1)", border: "1px solid rgba(255,171,0,0.3)",
            color: "#ffab00", padding: "0.2rem 0.6rem", borderRadius: 3, letterSpacing: "0.1em",
          }}>
            ⚠ DEMO SIMULATION MODE
          </span>

          {newAlertCount > 0 && (
            <span style={{
              background: "rgba(255,23,68,0.18)", border: "1px solid rgba(255,23,68,0.5)",
              color: "#ff1744", padding: "0.2rem 0.6rem", borderRadius: 3,
              fontWeight: 700, animation: "pulse-slow 1.2s infinite",
            }}>
              {newAlertCount} ACTIVE ALERT{newAlertCount !== 1 ? "S" : ""}
            </span>
          )}
        </div>
      </div>

      {/* ── Main 2-column grid ─────────────────────────────────────────── */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0.85rem", alignItems: "start" }}>

        {/* ══ LEFT: Camera + Controls ══════════════════════════════════════ */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>

          {/* Camera panel */}
          <div style={{ background: "#0e141f", border: "1px solid rgba(255,255,255,0.08)", borderRadius: 6, overflow: "hidden" }}>

            {/* Camera header bar */}
            <div style={{
              display: "flex", justifyContent: "space-between", alignItems: "center",
              padding: "0.55rem 0.85rem",
              borderBottom: "1px solid rgba(255,255,255,0.06)",
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
                <Camera size={13} color="#00e5ff" />
                <span style={{ fontSize: "0.75rem", fontWeight: 700, letterSpacing: "0.1em", color: "#fff" }}>
                  {DEMO_CAMERA_ID}
                </span>
                <span style={{ fontSize: "0.65rem", color: "#334155" }}>|</span>
                <span style={{ fontSize: "0.65rem", letterSpacing: "0.05em", color: "#64748b" }}>{DEMO_LOCATION}</span>
              </div>
              <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: statusColor, display: "inline-block" }} />
                <span style={{ fontSize: "0.62rem", letterSpacing: "0.1em", color: statusColor }}>
                  {status === "RUNNING" ? "ACTIVE" : status === "PAUSED" ? "PAUSED" : status === "ENDED" ? "ENDED" : "STANDBY"}
                </span>
              </div>
            </div>

            {/* Video feed */}
            <div style={{ position: "relative", aspectRatio: "16/9", background: "#020406" }}>
              {videoError ? (
                <div style={{
                  position: "absolute", inset: 0, display: "flex", flexDirection: "column",
                  alignItems: "center", justifyContent: "center", gap: "0.5rem",
                }}>
                  <AlertTriangle size={22} color="#ff1744" />
                  <span style={{ fontSize: "0.72rem", letterSpacing: "0.14em", color: "#ff1744" }}>
                    VIDEO SOURCE UNAVAILABLE
                  </span>
                  <span style={{ fontSize: "0.62rem", color: "#334155", textAlign: "center", maxWidth: 280 }}>
                    Place your MP4 at:<br />
                    <span style={{ color: "#64748b" }}>frontend/public/videos/border-demo.mp4</span>
                  </span>
                </div>
              ) : (
                <video
                  ref={videoRef}
                  src={DEMO_VIDEO_PATH}
                  style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
                  onError={() => setVideoError(true)}
                  onLoadedMetadata={() => {
                    const v = videoRef.current;
                    if (v) setVideoDuration(v.duration);
                  }}
                  onEnded={() => setStatus("ENDED")}
                  playsInline
                  muted
                />
              )}

              {/* HUD overlays — always on top */}
              <div aria-hidden style={{
                position: "absolute", top: 8, left: 10, display: "flex", alignItems: "center", gap: 6, pointerEvents: "none",
              }}>
                {status === "RUNNING" && (
                  <span style={{ width: 7, height: 7, borderRadius: "50%", background: "#ff1744", display: "inline-block", animation: "pulse-slow 1s infinite" }} />
                )}
                <span style={{ fontSize: "0.6rem", letterSpacing: "0.18em", color: "rgba(255,255,255,0.75)" }}>
                  {status === "RUNNING" ? "● REC  LIVE" : status === "PAUSED" ? "⏸ PAUSED" : status === "ENDED" ? "■ ENDED" : "◌ STANDBY"}
                </span>
              </div>

              <div aria-hidden style={{ position: "absolute", top: 8, right: 10, fontSize: "0.58rem", letterSpacing: "0.12em", color: "rgba(255,255,255,0.4)", pointerEvents: "none" }}>
                SIMULATION / DEMO FEED
              </div>

              <div aria-hidden style={{ position: "absolute", bottom: 8, left: 10, fontSize: "0.6rem", letterSpacing: "0.08em", color: "rgba(255,255,255,0.4)", pointerEvents: "none" }}>
                {fmtTime(videoTime)}
              </div>

              {status === "IDLE" && !videoError && (
                <div style={{
                  position: "absolute", inset: 0, display: "flex", flexDirection: "column",
                  alignItems: "center", justifyContent: "center", background: "rgba(5,7,10,0.65)",
                  gap: "0.5rem", pointerEvents: "none",
                }}>
                  <Eye size={28} color="rgba(255,255,255,0.25)" />
                  <span style={{ fontSize: "0.72rem", letterSpacing: "0.2em", color: "rgba(255,255,255,0.35)" }}>
                    SIMULATION READY
                  </span>
                  <span style={{ fontSize: "0.6rem", letterSpacing: "0.1em", color: "rgba(255,255,255,0.2)" }}>
                    Press START to begin
                  </span>
                </div>
              )}
            </div>

            {/* Source strip */}
            <div style={{
              display: "flex", gap: "1.25rem", padding: "0.45rem 0.85rem",
              borderTop: "1px solid rgba(255,255,255,0.05)",
              fontSize: "0.6rem", letterSpacing: "0.07em", color: "#334155",
            }}>
              <span>SOURCE: <span style={{ color: "#00e5ff" }}>DEMO VIDEO FILE</span></span>
              <span>DETECTION: <span style={{ color: "#ffab00" }}>SIMULATED</span></span>
              <span>PIPELINE: <span style={{ color: "#64748b" }}>SOURCE-INDEPENDENT</span></span>
            </div>
          </div>

          {/* ── Simulation Controls ── */}
          <div style={{ ...panel }}>
            <div style={{ ...sectionLabel }}>
              <Activity size={11} color="#475569" />
              SIMULATION CONTROLS
            </div>

            <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.75rem" }}>
              {status !== "RUNNING" ? (
                <button
                  id="btn-start-simulation"
                  onClick={handleStart}
                  disabled={videoError || status === "ENDED"}
                  style={{
                    display: "flex", alignItems: "center", gap: "0.4rem",
                    padding: "0.5rem 1rem",
                    background: (videoError || status === "ENDED") ? "rgba(0,230,118,0.04)" : "rgba(0,230,118,0.14)",
                    border: "1px solid rgba(0,230,118,0.35)",
                    color: (videoError || status === "ENDED") ? "#1e3a2f" : "#00e676",
                    borderRadius: 4, cursor: (videoError || status === "ENDED") ? "not-allowed" : "pointer",
                    fontSize: "0.78rem", fontWeight: 700, letterSpacing: "0.08em", fontFamily: "inherit",
                  }}
                >
                  <Play size={13} />
                  {status === "PAUSED" ? "RESUME" : "START SIMULATION"}
                </button>
              ) : (
                <button
                  id="btn-pause-simulation"
                  onClick={handlePause}
                  style={{
                    display: "flex", alignItems: "center", gap: "0.4rem",
                    padding: "0.5rem 1rem",
                    background: "rgba(255,171,0,0.12)", border: "1px solid rgba(255,171,0,0.38)",
                    color: "#ffab00", borderRadius: 4, cursor: "pointer",
                    fontSize: "0.78rem", fontWeight: 700, letterSpacing: "0.08em", fontFamily: "inherit",
                  }}
                >
                  <Pause size={13} />
                  PAUSE
                </button>
              )}

              <button
                id="btn-restart-simulation"
                onClick={handleRestart}
                style={{
                  display: "flex", alignItems: "center", gap: "0.4rem",
                  padding: "0.5rem 0.75rem",
                  background: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.1)",
                  color: "#64748b", borderRadius: 4, cursor: "pointer",
                  fontSize: "0.75rem", fontWeight: 600, letterSpacing: "0.06em", fontFamily: "inherit",
                }}
              >
                <RotateCcw size={13} />
                RESTART
              </button>
            </div>

            {/* Timeline progress */}
            <div style={{ marginBottom: "0.4rem" }}>
              <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.6rem", color: "#475569", marginBottom: "0.3rem" }}>
                <span>TIMELINE  {fmtTime(videoTime)}</span>
                <span>{fmtTime(videoDuration)}</span>
              </div>
              <div style={{ height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 2, position: "relative" }}>
                <div style={{ height: "100%", width: `${progress}%`, background: status === "RUNNING" ? "#00e5ff" : "#334155", borderRadius: 2, transition: "width 0.1s linear" }} />
                {/* Event markers on timeline */}
                {videoDuration > 0 && DEMO_SCENARIO.map((e, i) => (
                  <div
                    key={i}
                    title={`${fmtTime(e.time)}: ${evtLabel(e.type)}`}
                    style={{
                      position: "absolute", top: -2, left: `${(e.time / videoDuration) * 100}%`,
                      width: 3, height: 8, borderRadius: 1,
                      background: firedIndices.includes(i)
                        ? (e.type === "ZONE_INTRUSION" ? "#ff1744" : "#ffab00")
                        : "rgba(255,255,255,0.18)",
                      transform: "translateX(-50%)",
                    }}
                  />
                ))}
              </div>
              <div style={{ display: "flex", gap: "0.4rem", marginTop: "0.4rem", fontSize: "0.58rem", flexWrap: "wrap" }}>
                {DEMO_SCENARIO.map((e, i) => (
                  <span key={i} style={{ color: firedIndices.includes(i) ? "#00e676" : "#1e293b" }}>
                    {firedIndices.includes(i) ? "✓" : "○"} {evtLabel(e.type).toLowerCase()} @{fmtTime(e.time)}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* ── Workflow trace ── */}
          {workflowTrace && (
            <div style={{
              background: "rgba(0,229,255,0.06)", border: "1px solid rgba(0,229,255,0.2)",
              borderRadius: 6, padding: "0.7rem 0.85rem",
              animation: "fadeIn 0.3s ease",
            }}>
              <div style={{ ...sectionLabel, marginBottom: "0.3rem", color: "#00e5ff" }}>
                <Zap size={11} color="#00e5ff" />
                WORKFLOW EXECUTED
              </div>
              <div style={{ fontSize: "0.7rem", color: "#94a3b8", letterSpacing: "0.02em", lineHeight: 1.5 }}>
                {workflowTrace}
              </div>
            </div>
          )}

          {/* ── Security Incidents ── */}
          {incidents.length > 0 && (
            <div style={{ background: "#0e141f", border: "1px solid rgba(255,23,68,0.2)", borderRadius: 6, padding: "0.85rem" }}>
              <div style={{ ...sectionLabel, color: "#ff1744" }}>
                <AlertTriangle size={11} color="#ff1744" />
                SECURITY INCIDENTS ({incidents.length})
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem" }}>
                {incidents.map((inc) => (
                  <div key={inc.id} style={{
                    background: "rgba(255,23,68,0.07)", border: "1px solid rgba(255,23,68,0.2)",
                    borderRadius: 4, padding: "0.6rem 0.75rem",
                  }}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "0.2rem" }}>
                      <span style={{ fontSize: "0.72rem", fontWeight: 700, color: "#ff1744", letterSpacing: "0.06em" }}>{inc.id}</span>
                      <span style={{ fontSize: "0.6rem", color: "#475569" }}>{new Date(inc.timestamp).toLocaleTimeString()}</span>
                    </div>
                    <div style={{ fontSize: "0.68rem", color: "#94a3b8" }}>{inc.description}</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>

        {/* ══ RIGHT: Detection + Alerts + Events ═══════════════════════════ */}
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>

          {/* Detection status */}
          <div style={{ ...panel }}>
            <div style={{ ...sectionLabel }}>
              <Eye size={11} color="#475569" />
              CURRENT DETECTION STATUS
            </div>

            {currentDetection ? (
              <div style={{
                background: currentDetection.type === "ZONE_INTRUSION" ? "rgba(255,23,68,0.08)" : "rgba(255,171,0,0.07)",
                border: `1px solid ${currentDetection.type === "ZONE_INTRUSION" ? "rgba(255,23,68,0.3)" : "rgba(255,171,0,0.25)"}`,
                borderRadius: 5, padding: "0.85rem",
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "0.5rem" }}>
                  <div style={{ fontSize: "1rem", fontWeight: 700, letterSpacing: "0.05em", color: "#f1f5f9" }}>
                    {evtIcon(currentDetection.type)} {evtLabel(currentDetection.type)}
                  </div>
                  <span style={{
                    fontSize: "0.58rem", letterSpacing: "0.1em",
                    background: "rgba(255,171,0,0.12)", border: "1px solid rgba(255,171,0,0.3)",
                    color: "#ffab00", padding: "0.15rem 0.45rem", borderRadius: 3,
                  }}>
                    SIMULATED DETECTION
                  </span>
                </div>
                <div style={{ fontSize: "0.72rem", color: "#94a3b8", marginBottom: "0.55rem", lineHeight: 1.4 }}>
                  {currentDetection.description}
                </div>
                <div style={{ display: "flex", gap: "1.25rem", fontSize: "0.65rem", flexWrap: "wrap" }}>
                  {currentDetection.confidence !== undefined && (
                    <span>
                      CONFIDENCE: <span style={{ color: "#00e676", fontWeight: 700 }}>
                        {Math.round(currentDetection.confidence * 100)}%
                      </span>
                    </span>
                  )}
                  <span>CAMERA: <span style={{ color: "#00e5ff" }}>{currentDetection.cameraId}</span></span>
                  <span style={{ color: "#475569" }}>T+{fmtTime(currentDetection.videoTime)}</span>
                  <span style={{ color: "#334155" }}>SRC: {currentDetection.source}</span>
                </div>
              </div>
            ) : (
              <div style={{
                background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.05)",
                borderRadius: 5, padding: "1.5rem", textAlign: "center",
                fontSize: "0.68rem", letterSpacing: "0.12em", color: "#1e293b",
              }}>
                {status === "IDLE" ? "AWAITING SIMULATION START" : "NO DETECTION ACTIVE"}
              </div>
            )}
          </div>

          {/* Alert panel */}
          <div style={{ ...panel }}>
            <div style={{ ...sectionLabel, justifyContent: "space-between" }}>
              <span style={{ display: "flex", alignItems: "center", gap: "0.35rem" }}>
                <AlertTriangle size={11} color="#475569" />
                ACTIVE ALERTS
              </span>
              {newAlertCount > 0 && (
                <span style={{ color: "#ff1744", fontWeight: 700, fontSize: "0.62rem" }}>
                  {newAlertCount} NEW
                </span>
              )}
            </div>

            {alerts.length === 0 ? (
              <div style={{ fontSize: "0.68rem", color: "#1e293b", textAlign: "center", padding: "1rem", letterSpacing: "0.1em" }}>
                NO ALERTS
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.45rem", maxHeight: "220px", overflowY: "auto" }}>
                {alerts.map((alert) => (
                  <div key={alert.id} style={{
                    background: alertBg(alert.severity),
                    border: `1px solid ${alertBorder(alert.severity)}`,
                    borderRadius: 4, padding: "0.6rem 0.75rem",
                    display: "flex", justifyContent: "space-between", alignItems: "flex-start",
                    opacity: alert.status === "ACKNOWLEDGED" ? 0.5 : 1,
                  }}>
                    <div>
                      <div style={{ fontSize: "0.78rem", fontWeight: 700, color: alertColor(alert.severity), letterSpacing: "0.04em", marginBottom: "0.2rem" }}>
                        {alert.title}
                      </div>
                      <div style={{ fontSize: "0.62rem", color: "#475569", display: "flex", gap: "0.65rem", flexWrap: "wrap" }}>
                        <span>{alert.id}</span>
                        <span>{alert.cameraId}</span>
                        <span>{new Date(alert.timestamp).toLocaleTimeString()}</span>
                        <span style={{ color: alert.status === "NEW" ? "#ff1744" : "#00e676", fontWeight: 700 }}>
                          {alert.status}
                        </span>
                      </div>
                    </div>
                    {alert.status === "NEW" && (
                      <button
                        onClick={() => handleAck(alert.id)}
                        style={{
                          display: "flex", alignItems: "center", gap: "0.25rem",
                          padding: "0.2rem 0.5rem", flexShrink: 0, marginLeft: "0.5rem",
                          background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)",
                          color: "#64748b", borderRadius: 3, cursor: "pointer",
                          fontSize: "0.6rem", fontFamily: "inherit", letterSpacing: "0.06em",
                        }}
                      >
                        <CheckCircle size={9} />
                        ACK
                      </button>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Event history */}
          <div style={{ ...panel }}>
            <div style={{ ...sectionLabel }}>
              <Clock size={11} color="#475569" />
              EVENT HISTORY ({events.length})
            </div>

            {events.length === 0 ? (
              <div style={{ fontSize: "0.68rem", color: "#1e293b", textAlign: "center", padding: "1rem", letterSpacing: "0.1em" }}>
                NO EVENTS LOGGED
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: "0.3rem", maxHeight: "280px", overflowY: "auto" }}>
                {events.map((evt) => (
                  <div key={evt.id} style={{
                    display: "flex", alignItems: "flex-start", gap: "0.6rem",
                    padding: "0.45rem 0.6rem",
                    background: "rgba(255,255,255,0.02)", borderRadius: 3,
                    borderLeft: `2px solid ${evtBorderColor(evt.type)}`,
                  }}>
                    <span style={{ fontSize: "0.85rem", flexShrink: 0, lineHeight: 1.3 }}>{evtIcon(evt.type)}</span>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: "0.7rem", color: "#f1f5f9", fontWeight: 600, letterSpacing: "0.02em" }}>
                        {evtLabel(evt.type)}
                      </div>
                      <div style={{ fontSize: "0.6rem", color: "#475569", marginTop: "0.1rem" }}>
                        {evt.cameraId} · T+{fmtTime(evt.videoTime)}
                        {evt.confidence !== undefined && ` · ${Math.round(evt.confidence * 100)}% conf`}
                        {" · "}{evt.source}
                      </div>
                    </div>
                    <span style={{ fontSize: "0.58rem", color: "#334155", flexShrink: 0 }}>
                      {new Date(evt.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Architecture note — for judges */}
          <div style={{
            background: "rgba(0,229,255,0.03)", border: "1px solid rgba(0,229,255,0.08)",
            borderRadius: 6, padding: "0.75rem 0.85rem",
            fontSize: "0.62rem", color: "#334155", lineHeight: 1.7,
          }}>
            <span style={{ color: "#00e5ff", fontWeight: 700, display: "block", marginBottom: "0.2rem", letterSpacing: "0.08em" }}>
              SOURCE ABSTRACTION
            </span>
            This pipeline (Event → Workflow Rule → Alert) is source-independent.
            {" "}Replace <span style={{ color: "#64748b" }}>DemoVideoSource</span> with{" "}
            <span style={{ color: "#64748b" }}>LiveCameraSource</span> (RTSP / WebRTC)
            {" "}without rewriting the detection rules or dashboard logic.
          </div>
        </div>
      </div>
    </div>
  );
}
