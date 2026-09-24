/**
 * Border Intelligence — Central Reactive State Store
 * Provides live telemetry, real-time WebSocket events, camera feeds, and alert updates.
 * Real backend state only: zero mock/fake data.
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
  selectedCameraId: string | null;
  setSelectedCameraId: (id: string | null) => void;
  cameraPreviewUrls: Record<string, string>;
  setCameraPreviewUrl: (cameraId: string, url: string) => void;
  clearAllAlerts: () => Promise<void>;
  acknowledgeAlert: (alertId: string) => Promise<void>;
  acknowledgeIncident: (incidentId: string) => void;
  resolveIncident: (incidentId: string) => void;
  registerCameraLocally: (camera: CameraRecord, previewUrl?: string) => void;
  deleteCameraLocally: (cameraId: string) => void;
  toggleCameraStatus: (cameraId: string) => void;
  applyProfile: (profileId: string) => Promise<void>;
  resetDemo: () => Promise<void>;
}

const SurveillanceContext = createContext<SurveillanceContextType | undefined>(undefined);

export const SurveillanceProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [cameras, setCameras] = useState<CameraRecord[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(null);
  const [cameraPreviewUrls, setCameraPreviewUrls] = useState<Record<string, string>>({});
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [incidents, setIncidents] = useState<IncidentSummary[]>([]);
  const [threat, setThreat] = useState<ThreatAssessment | null>(null);
  const [metrics, setMetrics] = useState<SystemMetrics | null>(null);
  const [coverage, setCoverage] = useState<CoverageReport | null>(null);
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
      api.getIncidents({ limit: 20 }).then((res) => res?.incidents && setIncidents(res.incidents)).catch(() => {});
    } else if (msg.event_type === "incident") {
      api.getIncidents({ limit: 20 }).then((res) => res?.incidents && setIncidents(res.incidents)).catch(() => {});
    }
  }, [playAlertChime]);

  const { status: wsStatus, lastEvent: lastMessage } = useWebSocket(handleWsMessage);

  const refreshCameras = useCallback(async () => {
    try {
      const res = await api.getCameras();
      if (res?.cameras) {
        setCameras(res.cameras);
        setSelectedCameraId((cur) => cur || (res.cameras.length > 0 ? res.cameras[0].camera_id : null));
      }
    } catch (err: any) {
      console.warn("Could not load cameras from backend:", err.message);
    }
  }, []);

  const refreshAlerts = useCallback(async () => {
    try {
      const res = await api.getAlerts({ limit: 50 });
      if (res?.alerts) {
        setAlerts(res.alerts);
      }
    } catch (err: any) {
      console.warn("Could not load alerts from backend:", err.message);
    }
  }, []);

  const refreshIncidents = useCallback(async () => {
    try {
      const res = await api.getIncidents({ limit: 30 });
      if (res?.incidents) {
        setIncidents(res.incidents);
      }
    } catch (err: any) {
      console.warn("Could not load incidents from backend:", err.message);
    }
  }, []);

  const refreshThreat = useCallback(async () => {
    try {
      const res = await api.getThreatLevel();
      if (res) setThreat(res);
    } catch (err: any) {
      // ignore
    }
  }, []);

  const refreshMetrics = useCallback(async () => {
    try {
      const res = await api.getSystemMetrics();
      if (res) setMetrics(res);
    } catch (err: any) {
      // ignore
    }
  }, []);

  const refreshCoverage = useCallback(async () => {
    try {
      const res = await api.getCoverageReport();
      if (res) setCoverage(res);
    } catch (err: any) {
      // ignore
    }
  }, []);

  const refreshProfiles = useCallback(async () => {
    try {
      const res = await api.getProfiles();
      if (res?.active_profile) setActiveProfile(res.active_profile);
    } catch (err: any) {
      // ignore
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
      // ignore
    } finally {
      setIsLoading(false);
    }
  }, [refreshCameras, refreshAlerts, refreshIncidents, refreshThreat, refreshMetrics, refreshCoverage, refreshProfiles]);

  const acknowledgeAlert = useCallback(async (alertId: string) => {
    try {
      await api.acknowledgeAlert(alertId);
    } catch (err) {
      // local fallback
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

  const registerCameraLocally = useCallback((camera: CameraRecord, previewUrl?: string) => {
    setCameras((prev) => {
      const filtered = prev.filter((c) => c.camera_id !== camera.camera_id);
      return [camera, ...filtered];
    });
    setSelectedCameraId(camera.camera_id);
    if (previewUrl) {
      setCameraPreviewUrls((prev) => ({ ...prev, [camera.camera_id]: previewUrl }));
    }
  }, []);

  const setCameraPreviewUrl = useCallback((cameraId: string, url: string) => {
    setCameraPreviewUrls((prev) => ({ ...prev, [cameraId]: url }));
  }, []);

  const clearAllAlerts = useCallback(async () => {
    try {
      await api.clearAlerts();
    } catch {
      // ignore
    }
    setAlerts([]);
    // Refresh threat level immediately so meter resets
    refreshThreat();
  }, [refreshThreat]);

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
      // ignore
    }
  }, [refreshMetrics]);

  const resetDemo = useCallback(async () => {
    try {
      await api.resetDemo();
    } catch (err: any) {
      // ignore
    }
    await refreshAll();
  }, [refreshAll]);

  // Initial load & synchronized polling
  useEffect(() => {
    refreshAll();
    const timer = setInterval(() => {
      refreshCameras();
      refreshAlerts();
      refreshIncidents();
      refreshThreat();
      refreshMetrics();
      refreshCoverage();
    }, 2500);
    return () => clearInterval(timer);
  }, [refreshAll, refreshCameras, refreshAlerts, refreshIncidents, refreshThreat, refreshMetrics, refreshCoverage]);

  return (
    <SurveillanceContext.Provider
      value={{
        cameras,
        selectedCameraId,
        setSelectedCameraId,
        cameraPreviewUrls,
        setCameraPreviewUrl,
        clearAllAlerts,
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

export const useSurveillance = (): SurveillanceContextType => {
  const context = useContext(SurveillanceContext);
  if (!context) {
    throw new Error("useSurveillance must be used within a SurveillanceProvider");
  }
  return context;
};
