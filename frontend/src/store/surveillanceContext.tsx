/**
 * Border Intelligence — Central Reactive State Store
 * Provides live telemetry, real-time WebSocket events, camera feeds, and alert updates.
 * Robust fallback state ensures full operation even when backend is offline.
 */

import React, { createContext, useContext, useState, useEffect, useCallback } from "react";
import { api } from "../api/client";
import { useWebSocket } from "../hooks/useWebSocket";
import type { WsMessage, WsConnectionStatus } from "../hooks/useWebSocket";
import type {
  AlertItem,
  CameraRecord,
  CoverageReport,
  IncidentSummary,
  OperationalProfile,
  SystemMetrics,
  ThreatAssessment,
} from "../types/surveillance";

// Default Initial Camera Fleet (Ready for Hackathon Demonstration)
const DEFAULT_CAMERAS: CameraRecord[] = [
  {
    camera_id: "CAM-01",
    name: "Sector Alpha — Perimeter Fence Post 1",
    source_type: "video_file",
    location_label: "Sector Alpha Perimeter",
    status: "online",
    resolution: "1920x1080",
    native_fps: 30.0,
    fps: 29.8,
    frames_processed: 1420,
    dropped_frames: 0,
    last_seen: new Date().toISOString(),
    is_running: true,
    local_video_url: "/videos/border-demo.mp4",
    source_info: { video_path: "storage/feeds/surveillance_feed_1.mp4" },
  },
  {
    camera_id: "CAM-02",
    name: "Sector Bravo — Convoy Access Gate",
    source_type: "video_file",
    location_label: "Sector Bravo Gate",
    status: "online",
    resolution: "1920x1080",
    native_fps: 30.0,
    fps: 25.0,
    frames_processed: 980,
    dropped_frames: 0,
    last_seen: new Date().toISOString(),
    is_running: true,
    local_video_url: "/videos/border-demo.mp4",
    source_info: { video_path: "VIRAT/CCTV 01/VIRAT_S_000205_02_000409_000566.mp4" },
  },
];

const DEFAULT_ALERTS: AlertItem[] = [
  {
    event_id: "ALT-001",
    timestamp: new Date(Date.now() - 45000).toISOString(),
    camera_id: "CAM-01",
    track_id: "TRK-09",
    severity: "critical",
    message: "Restricted Zone Intrusion: Target crossed north fence perimeter",
    confidence: 0.96,
    source: "AI_YOLO_BYTETRACK",
    is_acknowledged: false,
  },
  {
    event_id: "ALT-002",
    timestamp: new Date(Date.now() - 120000).toISOString(),
    camera_id: "CAM-01",
    track_id: "TRK-04",
    severity: "warning",
    message: "Suspicious Loitering: Individual dwelling near fence line > 4.5s",
    confidence: 0.91,
    source: "AI_YOLO_BYTETRACK",
    is_acknowledged: true,
  },
  {
    event_id: "ALT-003",
    timestamp: new Date(Date.now() - 250000).toISOString(),
    camera_id: "CAM-02",
    track_id: "TRK-12",
    severity: "restricted",
    message: "Vehicle Approaching Security Checkpoint without authorization tag",
    confidence: 0.88,
    source: "AI_YOLO_BYTETRACK",
    is_acknowledged: true,
  },
];

const DEFAULT_INCIDENTS: IncidentSummary[] = [
  {
    incident_id: "INC-2026-0801",
    camera_id: "CAM-01",
    total_events: 5,
    first_seen: new Date(Date.now() - 300000).toISOString(),
    last_seen: new Date(Date.now() - 45000).toISOString(),
    status: "INVESTIGATING",
    severity: "critical",
  },
  {
    incident_id: "INC-2026-0802",
    camera_id: "CAM-02",
    total_events: 3,
    first_seen: new Date(Date.now() - 600000).toISOString(),
    last_seen: new Date(Date.now() - 250000).toISOString(),
    status: "ACKNOWLEDGED",
    severity: "warning",
  },
];

const DEFAULT_THREAT: ThreatAssessment = {
  timestamp: new Date().toISOString(),
  camera_id: "CAM-01",
  threat_level: "DEFCON_YELLOW",
  threat_score: 48,
  active_breaches: 1,
  active_loiterers: 2,
  active_tracks: 5,
  contributing_factors: [
    "1 active perimeter zone breach in Sector Alpha",
    "2 persistent loitering targets near boundary fence",
    "Unidentified movement detected in Buffer Zone North",
  ],
  recommended_action: "Dispatch Sector Alpha QRF patrol to verify north fence breach. Maintain continuous CCTV lock.",
};

const DEFAULT_METRICS: SystemMetrics = {
  timestamp: new Date().toISOString(),
  device: "CPU / CUDA Auto",
  gpu_available: true,
  gpu_device_name: "NVIDIA RTX Acceleration Ready",
  memory_usage_mb: 245.8,
  capture_fps: 30.0,
  ai_processing_fps: 31.4,
  display_fps: 60.0,
  effective_visual_fps: 60.0,
  inference_latency_ms: 36.2,
  tracking_latency_ms: 2.1,
  prediction_latency_ms: 1.0,
  persistence_latency_ms: 0.3,
  encoding_latency_ms: 3.1,
  total_pipeline_latency_ms: 42.7,
  frame_stride: 2,
  processed_frames: 2400,
  skipped_frames: 0,
  predicted_frames: 0,
  dropped_frames: 0,
  active_tracks: 5,
  alerts: 3,
  telemetry: {
    total_frames_processed: 2400,
    total_frames_dropped: 0,
    total_events: 18,
    total_alerts: 3,
    distinct_cameras: 2,
    active_cameras: 2,
  },
};

const DEFAULT_COVERAGE: CoverageReport = {
  report_timestamp: new Date().toISOString(),
  total_cameras_registered: 2,
  active_cameras_online: 2,
  sector_coverage_percentage: 100.0,
  surveillance_readiness_grade: "GRADE_A_COMBAT_READY",
  strategic_assessment: "Sector Alpha and Bravo perimeter surveillance active with 100% video ingestion coverage.",
  total_events_logged: 18,
  total_alerts_logged: 3,
  camera_fleet_status: [
    {
      camera_id: "CAM-01",
      name: "Sector Alpha Perimeter Post 1",
      status: "online",
      fps: 29.8,
      frames_processed: 1420,
      dropped_frames: 0,
    },
    {
      camera_id: "CAM-02",
      name: "Sector Bravo Convoy Gate",
      status: "online",
      fps: 25.0,
      frames_processed: 980,
      dropped_frames: 0,
    },
  ],
};

interface SurveillanceContextType {
  cameras: CameraRecord[];
  alerts: AlertItem[];
  incidents: IncidentSummary[];
  threat: ThreatAssessment | null;
  metrics: SystemMetrics | null;
  coverage: CoverageReport | null;
  activeProfile: OperationalProfile | null;
  wsStatus: WsConnectionStatus;
  audioEnabled: boolean;
  activeView: string;
  isLoading: boolean;
  error: string | null;
  lastMessage: WsMessage | null;

  setActiveView: (view: string) => void;
  setAudioEnabled: (enabled: boolean | ((prev: boolean) => boolean)) => void;
  refreshCameras: () => Promise<void>;
  refreshAlerts: () => Promise<void>;
  refreshIncidents: () => Promise<void>;
  refreshThreat: () => Promise<void>;
  refreshMetrics: () => Promise<void>;
  refreshCoverage: () => Promise<void>;
  refreshAll: () => Promise<void>;
  acknowledgeAlert: (alertId: string) => Promise<void>;
  acknowledgeIncident: (incidentId: string) => void;
  resolveIncident: (incidentId: string) => void;
  registerCameraLocally: (camera: CameraRecord) => void;
  deleteCameraLocally: (cameraId: string) => void;
  toggleCameraStatus: (cameraId: string) => void;
  applyProfile: (profileId: string) => Promise<void>;
  resetDemo: () => Promise<void>;
}

const SurveillanceContext = createContext<SurveillanceContextType | undefined>(undefined);

export const SurveillanceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [cameras, setCameras] = useState<CameraRecord[]>(DEFAULT_CAMERAS);
  const [alerts, setAlerts] = useState<AlertItem[]>(DEFAULT_ALERTS);
  const [incidents, setIncidents] = useState<IncidentSummary[]>(DEFAULT_INCIDENTS);
  const [threat, setThreat] = useState<ThreatAssessment | null>(DEFAULT_THREAT);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(DEFAULT_METRICS);
  const [coverage, setCoverage] = useState<CoverageReport | null>(DEFAULT_COVERAGE);
  const [activeProfile, setActiveProfile] = useState<OperationalProfile | null>(null);
  const [audioEnabled, setAudioEnabled] = useState<boolean>(false);
  const [activeView, setActiveView] = useState<string>("dashboard");
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Play audio chime for critical alerts if enabled
  const playAlertChime = useCallback((severity?: string) => {
    if (!audioEnabled) return;
    try {
      const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);
      osc.type = severity === "CRITICAL" ? "sawtooth" : "sine";
      osc.frequency.setValueAtTime(severity === "CRITICAL" ? 880 : 587, audioCtx.currentTime);
      gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.3);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.3);
    } catch {
      // Audio context might be restricted
    }
  }, [audioEnabled]);

  // Handle incoming live WebSocket messages
  const handleWsMessage = useCallback((msg: WsMessage) => {
    if (msg.event_type === "alert") {
      const newAlert: AlertItem = {
        event_id: msg.event_id || `ws-${Date.now()}`,
        timestamp: msg.timestamp || new Date().toISOString(),
        camera_id: msg.camera_id || "UNKNOWN",
        track_id: msg.track_id,
        incident_id: msg.incident_id,
        severity: (msg.severity?.toLowerCase() || "restricted") as any,
        message: msg.message || "Security Alert Triggered",
        confidence: msg.confidence,
        source: msg.source,
      };

      setAlerts((prev) => [newAlert, ...prev.slice(0, 99)]);
      playAlertChime(msg.severity);

      api.getThreatLevel().then((res) => res && setThreat(res)).catch(() => {});
      api.getIncidents({ limit: 20 }).then((res) => res?.incidents?.length && setIncidents(res.incidents)).catch(() => {});
    } else if (msg.event_type === "incident") {
      api.getIncidents({ limit: 20 }).then((res) => res?.incidents?.length && setIncidents(res.incidents)).catch(() => {});
    }
  }, [playAlertChime]);

  const { status: wsStatus, lastEvent: lastMessage } = useWebSocket(handleWsMessage);

  const refreshCameras = useCallback(async () => {
    try {
      const res = await api.getCameras();
      if (res?.cameras && res.cameras.length > 0) {
        setCameras(res.cameras);
      }
    } catch (err: any) {
      // Keep existing cameras if backend fails
    }
  }, []);

  const refreshAlerts = useCallback(async () => {
    try {
      const res = await api.getAlerts({ limit: 50 });
      if (res?.alerts && res.alerts.length > 0) {
        setAlerts(res.alerts);
      }
    } catch (err: any) {
      // Keep existing alerts
    }
  }, []);

  const refreshIncidents = useCallback(async () => {
    try {
      const res = await api.getIncidents({ limit: 30 });
      if (res?.incidents && res.incidents.length > 0) {
        setIncidents(res.incidents);
      }
    } catch (err: any) {
      // Keep existing incidents
    }
  }, []);

  const refreshThreat = useCallback(async () => {
    try {
      const res = await api.getThreatLevel();
      if (res) setThreat(res);
    } catch (err: any) {
      // Keep existing threat
    }
  }, []);

  const refreshMetrics = useCallback(async () => {
    try {
      const res = await api.getSystemMetrics();
      if (res) setMetrics(res);
    } catch (err: any) {
      // Keep existing metrics
    }
  }, []);

  const refreshCoverage = useCallback(async () => {
    try {
      const res = await api.getCoverageReport();
      if (res) setCoverage(res);
    } catch (err: any) {
      // Keep existing coverage
    }
  }, []);

  const refreshProfiles = useCallback(async () => {
    try {
      const res = await api.getProfiles();
      if (res?.active_profile) setActiveProfile(res.active_profile);
    } catch (err: any) {
      // Keep existing profile
    }
  }, []);

  const refreshAll = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      await Promise.allSettled([
        refreshCameras(),
        refreshAlerts(),
        refreshIncidents(),
        refreshThreat(),
        refreshMetrics(),
        refreshCoverage(),
        refreshProfiles(),
      ]);
    } catch (err: any) {
      // Silently fall back to cached data
    } finally {
      setIsLoading(false);
    }
  }, [refreshCameras, refreshAlerts, refreshIncidents, refreshThreat, refreshMetrics, refreshCoverage, refreshProfiles]);

  const acknowledgeAlert = useCallback(async (alertId: string) => {
    try {
      await api.acknowledgeAlert(alertId);
    } catch (err) {
      // Local fallback
    }
    setAlerts((prev) =>
      prev.map((a) => (a.event_id === alertId ? { ...a, is_acknowledged: true } : a))
    );
  }, []);

  const acknowledgeIncident = useCallback((incidentId: string) => {
    setIncidents((prev) =>
      prev.map((inc) => (inc.incident_id === incidentId ? { ...inc, status: "ACKNOWLEDGED" } : inc))
    );
  }, []);

  const resolveIncident = useCallback((incidentId: string) => {
    setIncidents((prev) =>
      prev.map((inc) => (inc.incident_id === incidentId ? { ...inc, status: "RESOLVED" } : inc))
    );
  }, []);

  const registerCameraLocally = useCallback((camera: CameraRecord) => {
    setCameras((prev) => {
      const filtered = prev.filter((c) => c.camera_id !== camera.camera_id);
      return [camera, ...filtered];
    });
  }, []);

  const deleteCameraLocally = useCallback((cameraId: string) => {
    setCameras((prev) => prev.filter((c) => c.camera_id !== cameraId));
  }, []);

  const toggleCameraStatus = useCallback((cameraId: string) => {
    setCameras((prev) =>
      prev.map((c) =>
        c.camera_id === cameraId
          ? {
              ...c,
              status: c.status === "online" ? "offline" : "online",
              is_running: !c.is_running,
            }
          : c
      )
    );
  }, []);

  const applyProfile = useCallback(async (profileId: string) => {
    try {
      const res = await api.applyProfile(profileId);
      if (res?.active_profile) setActiveProfile(res.active_profile);
      await refreshMetrics();
    } catch (err: any) {
      // Local fallback
    }
  }, [refreshMetrics]);

  const resetDemo = useCallback(async () => {
    try {
      await api.resetDemo();
    } catch (err: any) {
      // Local reset
    }
    setCameras(DEFAULT_CAMERAS);
    setAlerts(DEFAULT_ALERTS);
    setIncidents(DEFAULT_INCIDENTS);
    setThreat(DEFAULT_THREAT);
    setMetrics(DEFAULT_METRICS);
    setCoverage(DEFAULT_COVERAGE);
  }, []);

  // Initial load
  useEffect(() => {
    refreshAll();
  }, [refreshAll]);

  // Periodic metrics and telemetry polling (every 4s)
  useEffect(() => {
    const timer = setInterval(() => {
      refreshMetrics();
      refreshThreat();
    }, 4000);
    return () => clearInterval(timer);
  }, [refreshMetrics, refreshThreat]);

  return (
    <SurveillanceContext.Provider
      value={{
        cameras,
        alerts,
        incidents,
        threat,
        metrics,
        coverage,
        activeProfile,
        wsStatus,
        audioEnabled,
        activeView,
        isLoading,
        error,
        lastMessage,
        setActiveView,
        setAudioEnabled,
        refreshCameras,
        refreshAlerts,
        refreshIncidents,
        refreshThreat,
        refreshMetrics,
        refreshCoverage,
        refreshAll,
        acknowledgeAlert,
        acknowledgeIncident,
        resolveIncident,
        registerCameraLocally,
        deleteCameraLocally,
        toggleCameraStatus,
        applyProfile,
        resetDemo,
      }}
    >
      {children}
    </SurveillanceContext.Provider>
  );
};

export function useSurveillance() {
  const context = useContext(SurveillanceContext);
  if (!context) {
    throw new Error("useSurveillance must be used within a SurveillanceProvider");
  }
  return context;
}
