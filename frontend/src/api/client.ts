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

export const API_BASE_URL = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
export const WS_BASE_URL = import.meta.env.VITE_WS_URL || "ws://127.0.0.1:8000/ws/events";

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
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
        throw new Error(errorDetail);
      }
      return (await response.json()) as T;
    } catch (err: any) {
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
    location_label?: string;
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
        let err = `HTTP ${res.status}`;
        try {
          const body = await res.json();
          if (body.detail) err = body.detail;
        } catch {}
        throw new Error(err);
      }
      return res.json() as Promise<CameraRecord>;
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

  getCameraDiagnostics(cameraId: string) {
    return this.request<CameraDiagnostics>(`/api/cameras/${cameraId}/diagnostics`);
  }

  getCameraHeatmap(cameraId: string) {
    return this.request<HeatmapResponse>(`/api/cameras/${cameraId}/heatmap`);
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
    zone_id: string;
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
    boundary_id: string;
    name: string;
    pt1: [number, number];
    pt2: [number, number];
    severity: string;
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

  getRawStreamUrl(cameraId: string) {
    return `${this.baseUrl}/api/stream/raw/${cameraId}`;
  }
}

export const api = new ApiClient();
