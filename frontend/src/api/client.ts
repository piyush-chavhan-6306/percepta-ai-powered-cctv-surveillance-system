/**
 * Border Intelligence — Full REST API Client
 * Connects to FastAPI backend at http://127.0.0.1:8000
 */

import type {
  AlertsResponse,
  AuditLogEntry,
  CameraDiagnostics,
  CameraListResponse,
  CameraRecord,
  CoverageReport,
  DatabaseDiagnostics,
  EvidenceVerificationResult,
  ForensicVerificationResult,
  GroundedIntelligenceResponse,
  HeatmapResponse,
  IncidentDossier,
  IncidentSummary,
  IncidentTimelineResponse,
  IntegrityAuditReport,
  MultiModalSensorsStatus,
  OperationalProfile,
  OperatorAnnotation,
  SnapshotMetadata,
  SystemMetrics,
  ThreatAssessment,
  ZoneTemplate,
  ZonesListResponse,
} from "../types/surveillance";

function getComputedApiBaseUrl(): string {
  if (typeof window !== "undefined") {
    const saved = localStorage.getItem("percepta_backend_url");
    if (saved && saved.trim()) {
      return saved.trim().replace(/\/+$/, "");
    }
  }
  if (import.meta.env.VITE_API_URL) {
    return import.meta.env.VITE_API_URL.replace(/\/+$/, "");
  }
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host !== "localhost" && host !== "127.0.0.1") {
      return "";
    }
  }
  return "http://127.0.0.1:8000";
}

function getComputedWsBaseUrl(): string {
  if (typeof window !== "undefined") {
    const savedWs = localStorage.getItem("percepta_ws_url");
    if (savedWs && savedWs.trim()) {
      return savedWs.trim();
    }
    const savedBackend = localStorage.getItem("percepta_backend_url");
    if (savedBackend && savedBackend.trim()) {
      try {
        const u = new URL(savedBackend.trim());
        const proto = u.protocol === "https:" ? "wss:" : "ws:";
        return `${proto}//${u.host}/ws/events`;
      } catch {}
    }
  }
  if (import.meta.env.VITE_WS_URL) {
    return import.meta.env.VITE_WS_URL;
  }
  if (import.meta.env.VITE_API_URL) {
    try {
      const u = new URL(import.meta.env.VITE_API_URL);
      const proto = u.protocol === "https:" ? "wss:" : "ws:";
      return `${proto}//${u.host}/ws/events`;
    } catch {}
  }
  if (typeof window !== "undefined") {
    const host = window.location.hostname;
    if (host !== "localhost" && host !== "127.0.0.1") {
      const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
      return `${proto}//${window.location.host}/ws/events`;
    }
  }
  return "ws://127.0.0.1:8000/ws/events";
}

export const API_BASE_URL = getComputedApiBaseUrl();
export const WS_BASE_URL = getComputedWsBaseUrl();

export interface ApiClientError extends Error {
  status?: number;
  statusText?: string;
  url?: string;
  endpoint?: string;
  isNetworkError?: boolean;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  getBaseUrl(): string {
    return this.baseUrl;
  }

  setBaseUrl(newUrl: string) {
    const cleaned = (newUrl || "").trim().replace(/\/+$/, "");
    this.baseUrl = cleaned;
    if (typeof window !== "undefined") {
      if (cleaned) {
        localStorage.setItem("percepta_backend_url", cleaned);
      } else {
        localStorage.removeItem("percepta_backend_url");
      }
    }
  }

  async probeHealth(targetUrl?: string): Promise<{ ok: boolean; status: number; service?: string; error?: string }> {
    const base = targetUrl !== undefined ? targetUrl.replace(/\/+$/, "") : this.baseUrl;
    const url = `${base}/api/health`;
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 3000);
      const response = await fetch(url, { signal: controller.signal });
      clearTimeout(timeoutId);
      if (response.ok) {
        const data = await response.json();
        return { ok: true, status: response.status, service: data.service || "PERCEPTA Gateway" };
      }
      return { ok: false, status: response.status, error: `HTTP ${response.status} ${response.statusText}` };
    } catch (err: any) {
      const isAbort = err.name === "AbortError";
      return {
        ok: false,
        status: 0,
        error: isAbort ? "Request timed out (3.0s)" : err.message || "Connection refused / network unreachable",
      };
    }
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    };

    try {
      const response = await fetch(url, { ...options, headers });
      if (!response.ok) {
        let errorDetail = `HTTP ${response.status} ${response.statusText}`;
        try {
          const body = await response.json();
          if (body.detail) {
            errorDetail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
          }
        } catch {
          // ignore json parse error
        }
        const err = new Error(errorDetail) as ApiClientError;
        err.status = response.status;
        err.statusText = response.statusText;
        err.url = url;
        err.endpoint = endpoint;
        throw err;
      }
      const contentType = response.headers.get("content-type") || "";
      if (!contentType.includes("application/json")) {
        const err = new Error(`Endpoint ${endpoint} returned non-JSON response (${contentType || 'empty'})`) as ApiClientError;
        err.status = response.status;
        err.isNetworkError = true;
        throw err;
      }
      return (await response.json()) as T;
    } catch (err: any) {
      if (!err.status) {
        err.isNetworkError = true;
        err.endpoint = endpoint;
        err.url = url;
      }
      console.error(`API Error on [${options.method || "GET"}] ${endpoint}:`, err.message);
      throw err;
    }
  }

  // === System & Health ===
  getHealth() {
    return this.request<{ status: string; service: string; database: string }>("/api/health");
  }

  getReadiness() {
    return this.request<{ status: string; checks: Record<string, boolean> }>("/api/readiness");
  }

  getSystemStatus() {
    return this.request<any>("/api/system/status");
  }

  getSystemMetrics() {
    return this.request<SystemMetrics>("/api/system/metrics");
  }

  getCoverageReport() {
    return this.request<CoverageReport>("/api/system/coverage-report");
  }

  getProfiles() {
    return this.request<{ active_profile: OperationalProfile; available_profiles: OperationalProfile[] }>("/api/system/profiles");
  }

  applyProfile(profile_id: string) {
    return this.request<{ status: string; active_profile: OperationalProfile }>("/api/system/profiles/apply", {
      method: "POST",
      body: JSON.stringify({ profile_id }),
    });
  }

  getAuditLogs(limit: number = 100) {
    return this.request<{ count: number; audit_logs: AuditLogEntry[] }>(`/api/system/audit-logs?limit=${limit}`);
  }

  getDbDiagnostics() {
    return this.request<DatabaseDiagnostics>("/api/system/db-diagnostics");
  }

  resetDemo() {
    return this.request<{ status: string; message: string }>("/api/system/demo-reset", {
      method: "POST",
    });
  }

  // === Cameras ===
  getCameras() {
    return this.request<CameraListResponse>("/api/cameras");
  }

  getCamera(cameraId: string) {
    return this.request<CameraRecord>(`/api/cameras/${cameraId}`);
  }

  registerCamera(data: {
    camera_id: string;
    name?: string;
    source_type: string;
    source_url?: string;
    file_path?: string;
    location_label?: string;
    modality?: string;
    fps?: number;
    loop?: boolean;
    device_index?: number;
    autostart?: boolean;
  }) {
    return this.request<CameraRecord>("/api/cameras/register", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  uploadCameraVideo(formData: FormData) {
    const url = `${this.baseUrl}/api/cameras/upload`;
    return fetch(url, {
      method: "POST",
      body: formData,
    }).then(async (res) => {
      if (!res.ok) {
        let errText = `HTTP ${res.status} ${res.statusText}`;
        try {
          const body = await res.json();
          if (body.detail) errText = body.detail;
        } catch {}
        const err = new Error(errText) as ApiClientError;
        err.status = res.status;
        err.statusText = res.statusText;
        err.url = url;
        err.endpoint = "/api/cameras/upload";
        throw err;
      }
      return res.json() as Promise<CameraRecord>;
    }).catch((err) => {
      if (!err.status) {
        err.isNetworkError = true;
        err.endpoint = "/api/cameras/upload";
        err.url = url;
      }
      throw err;
    });
  }

  getAvailableSources() {
    return this.request<{
      bundled_clips: Array<{ name: string; path: string; size_mb: number }>;
      uploaded_clips: Array<{ name: string; path: string; size_mb: number }>;
      total_count: number;
    }>("/api/cameras/sources/available");
  }

  startCamera(cameraId: string) {
    return this.request<{ camera_id: string; status: string }>(`/api/cameras/${cameraId}/start`, { method: "POST" });
  }

  stopCamera(cameraId: string) {
    return this.request<{ camera_id: string; status: string }>(`/api/cameras/${cameraId}/stop`, { method: "POST" });
  }

  deleteCamera(cameraId: string) {
    return this.request<{ camera_id: string; status: string }>(`/api/cameras/${cameraId}`, { method: "DELETE" });
  }

  pauseAnalysis(cameraId: string) {
    return this.request<{ camera_id: string; status: string }>(`/api/cameras/${cameraId}/pause`, { method: "POST" });
  }

  resumeAnalysis(cameraId: string) {
    return this.request<{ camera_id: string; status: string }>(`/api/cameras/${cameraId}/resume`, { method: "POST" });
  }

  getCameraDiagnostics(cameraId: string) {
    return this.request<CameraDiagnostics>(`/api/cameras/${cameraId}/diagnostics`);
  }

  getCameraHeatmap(cameraId: string) {
    return this.request<HeatmapResponse>(`/api/cameras/${cameraId}/heatmap`);
  }

  getCameraMetrics(cameraId: string) {
    return this.request<{
      camera_id: string;
      source_fps: number;
      display_fps: number;
      inference_fps: number;
      inference_latency_ms: number;
      device: string;
      active_provider: string;
      track_count: number;
      worker_running: boolean;
      published_frames: number;
      read_latency_ms: number;
      encoding_latency_ms: number;
      last_error: string | null;
    }>(`/api/cameras/${cameraId}/metrics`);
  }

  // === Alerts & Incidents ===
  getAlerts(params?: { camera_id?: string; severity?: string; limit?: number }) {
    const q = new URLSearchParams();
    if (params?.camera_id) q.set("camera_id", params.camera_id);
    if (params?.severity) q.set("severity", params.severity);
    if (params?.limit) q.set("limit", params.limit.toString());
    const queryStr = q.toString() ? `?${q.toString()}` : "";
    return this.request<AlertsResponse>(`/api/alerts${queryStr}`);
  }

  acknowledgeAlert(alertId: string) {
    return this.request<{ event_id: string; status: string }>(`/api/alerts/${alertId}/ack`, {
      method: "POST",
    });
  }

  clearAlerts() {
    return this.request<{ status: string; message: string }>("/api/alerts/clear", {
      method: "POST",
    });
  }

  getIncidents(params?: { camera_id?: string; limit?: number }) {
    const q = new URLSearchParams();
    if (params?.camera_id) q.set("camera_id", params.camera_id);
    if (params?.limit) q.set("limit", params.limit.toString());
    const queryStr = q.toString() ? `?${q.toString()}` : "";
    return this.request<{ count: number; incidents: IncidentSummary[] }>(`/api/incidents${queryStr}`);
  }

  getIncidentTimeline(incidentId: string) {
    return this.request<IncidentTimelineResponse>(`/api/incidents/${incidentId}/timeline`);
  }

  getIncidentDossier(incidentId: string) {
    return this.request<IncidentDossier>(`/api/incidents/${incidentId}/dossier`);
  }

  getIncidentNotes(incidentId: string) {
    return this.request<{ incident_id: string; count: number; annotations: OperatorAnnotation[] }>(
      `/api/incidents/${incidentId}/notes`
    );
  }

  addIncidentNote(incidentId: string, data: { operator_callsign: string; note: string; disposition: string }) {
    return this.request<OperatorAnnotation>(`/api/incidents/${incidentId}/notes`, {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // === Zones & Boundaries ===
  getZones() {
    return this.request<ZonesListResponse>("/api/zones");
  }

  createZone(data: {
    zone_id?: string;
    name: string;
    polygon: number[][];
    severity: string;
    loitering_threshold_seconds?: number;
  }) {
    return this.request<any>("/api/zones", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  createBoundary(data: {
    boundary_id?: string;
    name: string;
    pt1: [number, number];
    pt2: [number, number];
    severity: string;
    direction?: string;
  }) {
    return this.request<any>("/api/zones/boundary", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  deleteZone(zoneId: string) {
    return this.request<{ zone_id: string; status: string }>(`/api/zones/${zoneId}`, { method: "DELETE" });
  }

  getZoneTemplates() {
    return this.request<{ templates: ZoneTemplate[] }>("/api/zones/templates");
  }

  applyZoneTemplate(template_id: string, zone_id_suffix: string = "01", custom_name?: string) {
    return this.request<any>("/api/zones/apply-template", {
      method: "POST",
      body: JSON.stringify({ template_id, zone_id_suffix, custom_name }),
    });
  }

  // === Threat & Forensics ===
  getThreatLevel(cameraId?: string) {
    const q = cameraId ? `?camera_id=${cameraId}` : "";
    return this.request<ThreatAssessment>(`/api/threat/level${q}`);
  }

  verifyEvent(eventId: string) {
    return this.request<ForensicVerificationResult>(`/api/evidence/verify/${eventId}`);
  }

  verifyEvidenceRecord(identifier: string) {
    return this.request<EvidenceVerificationResult>(`/api/evidence/verify-record/${encodeURIComponent(identifier)}`);
  }

  auditIntegrity(limit: number = 200) {
    return this.request<IntegrityAuditReport>(`/api/evidence/audit-integrity?limit=${limit}`);
  }

  getSnapshots(incidentId: string) {
    return this.request<{ incident_id: string; count: number; snapshots: SnapshotMetadata[] }>(
      `/api/evidence/snapshots/${incidentId}`
    );
  }

  getSnapshotFileUrl(filename: string) {
    return `${this.baseUrl}/api/evidence/snapshots/file/${filename}`;
  }

  getExportUrl(format: "json" | "csv", cameraId?: string, eventType?: string) {
    const q = new URLSearchParams({ format });
    if (cameraId) q.set("camera_id", cameraId);
    if (eventType) q.set("event_type", eventType);
    return `${this.baseUrl}/api/events/export?${q.toString()}`;
  }

  // === Multi-Modal Sensors ===
  getSensorsStatus() {
    return this.request<MultiModalSensorsStatus>("/api/sensors/status");
  }

  ingestSensorEvent(data: {
    sensor_id: string;
    sensor_type: string;
    sector_id: string;
    confidence: number;
    data: Record<string, any>;
  }) {
    return this.request<any>("/api/sensors/ingest", {
      method: "POST",
      body: JSON.stringify(data),
    });
  }

  // === Grounded AI Assistant ===
  queryIntelligence(query: string, cameraId?: string) {
    return this.request<GroundedIntelligenceResponse>("/api/intelligence/query", {
      method: "POST",
      body: JSON.stringify({ query, camera_id: cameraId || null }),
    });
  }

  // === Stream URLs ===
  getVideoStreamUrl(cameraId: string) {
    return `${this.baseUrl}/api/stream/video/${cameraId}`;
  }

  getCameraVideoFileUrl(cameraId: string) {
    return `${this.baseUrl}/api/cameras/${cameraId}/video`;
  }

  getRawStreamUrl(cameraId: string) {
    return `${this.baseUrl}/api/stream/raw/${cameraId}`;
  }
}

export const api = new ApiClient();
