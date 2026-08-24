# Border Intelligence — Backend-to-Frontend Integration Contract

**Project**: Border Intelligence — AI-Powered Persistent Border Surveillance & Incident Intelligence Platform  
**SIH Problem Statement**: PS SIH26187 ("AI-Based Intelligent Video Analytics Platform for Border Surveillance using existing CCTV Infrastructure")  
**Target Consumer**: React + Vite + TypeScript Command Center Frontend  
**Base URL**: `http://127.0.0.1:8000`  
**WebSocket URL**: `ws://127.0.0.1:8000/ws/events`  
**Status**: 🟢 **FROZEN & VERIFIED**

---

## 1. System Overview & Communication Protocols

The Border Intelligence platform communicates with the Command Center frontend across three channels:

1. **REST APIs (HTTP/JSON)**: CRUD camera management, incident timelines, historical event queries, system telemetry, and Grounded Intelligence Q&A.
2. **WebSocket (`/ws/events`)**: Real-time push stream of persisted surveillance events (`alert`, `zone`, `tracking`, `detection`, `incident`, `system`).
3. **MJPEG Stream (`/api/stream/video/{camera_id}`)**: Low-latency multipart JPEG video feed decoupled from AI processing ($>140\text{ FPS}$ streaming capability).

```mermaid
flowchart LR
    subgraph BACKEND["FastAPI Backend (Port 8000)"]
        REST["REST Endpoints (/api/...)"]
        WS["WebSocket (/ws/events)"]
        MJPEG["MJPEG (/api/stream/video/{id})"]
    end

    subgraph FRONTEND["React TypeScript Command Center"]
        HOOK_API["useAlerts / useSystemMetrics / useIntelligence"]
        HOOK_WS["useEventStream (Real-Time Events)"]
        CANVAS["SurveillanceCanvas (60-90 FPS Canvas / Video)"]
    end

    REST <--> HOOK_API
    WS --> HOOK_WS
    MJPEG --> CANVAS
```

---

## 2. REST Endpoints Reference

### 2.1 System Health & Readiness

#### `GET /api/health`
**Purpose**: Liveness probe verifying HTTP connectivity and database accessibility.

- **Response (200 OK)**:
```json
{
  "status": "healthy",
  "service": "Border Intelligence AI Layer",
  "timestamp": "2026-08-23T18:15:00.123456Z",
  "database": "connected",
  "mode": "P0_CORE"
}
```

#### `GET /api/readiness`
**Purpose**: Readiness probe checking that model weights, database, storage directories, and camera manager are initialized.

- **Response (200 OK)**:
```json
{
  "status": "ready",
  "timestamp": "2026-08-23T18:15:00.123456Z",
  "checks": {
    "database_connected": true,
    "model_file_present": true,
    "storage_directories": true,
    "camera_subsystem": true
  }
}
```

---

### 2.2 Camera Management

#### `GET /api/cameras`
**Purpose**: List all registered surveillance cameras, operational statuses, and current framerates.

- **Response (200 OK)**:
```json
{
  "count": 2,
  "cameras": [
    {
      "camera_id": "CAM-01",
      "name": "Sector Alpha North Gate",
      "source_type": "video_file",
      "location_label": "Sector Alpha Post 4",
      "status": "online",
      "resolution": "1280x720",
      "native_fps": 30.0,
      "fps": 30.0,
      "frames_processed": 1420,
      "dropped_frames": 0,
      "last_seen": "2026-08-23T18:15:02.100000Z",
      "is_running": true
    },
    {
      "camera_id": "CAM-02",
      "name": "Sector Bravo Perimeter",
      "source_type": "rtsp",
      "location_label": "Sector Bravo Tower 2",
      "status": "offline",
      "resolution": "1920x1080",
      "native_fps": 25.0,
      "fps": 25.0,
      "frames_processed": 0,
      "dropped_frames": 0,
      "last_seen": null,
      "is_running": false
    }
  ]
}
```

#### `GET /api/cameras/{camera_id}`
**Purpose**: Get details for a single camera. Returns `404 Not Found` if missing.

#### `POST /api/cameras/register`
**Purpose**: Dynamically register a new camera source (Video file, RTSP stream, or Simulation).

- **Request Body**:
```json
{
  "camera_id": "CAM-03",
  "name": "Sector Charlie Riverbed",
  "source_type": "rtsp",
  "source_url": "rtsp://admin:password@192.168.1.50:554/h264",
  "location_label": "Sector Charlie River Post",
  "loop": true,
  "fps": 25.0
}
```
*(Note: RTSP credentials are sanitized automatically; passwords are never returned in responses).*

#### `DELETE /api/cameras/{camera_id}`
**Purpose**: Deregister and safely stop a camera stream.

- **Response (200 OK)**:
```json
{
  "camera_id": "CAM-03",
  "status": "deregistered"
}
```

#### `POST /api/cameras/{camera_id}/start` & `POST /api/cameras/{camera_id}/stop`
**Purpose**: Start or stop live video capture on a registered camera.

- **Response (200 OK)**:
```json
{
  "camera_id": "CAM-01",
  "status": "started"
}
```

#### `POST /api/cameras/{camera_id}/reconnect`
**Purpose**: Force exponential backoff reconnection for a degraded or disconnected camera.

- **Response (200 OK)**:
```json
{
  "camera_id": "CAM-01",
  "status": "reconnected"
}
```

---

### 2.3 Live Alerts & Incidents

#### `GET /api/alerts`
**Purpose**: Query persisted security alerts with optional camera and severity filtering.

- **Query Parameters**:
  - `camera_id` (optional, string)
  - `severity` (optional, string: `"info"`, `"warning"`, `"restricted"`, `"critical"`)
  - `limit` (optional, integer, default: `50`)

- **Response (200 OK)**:
```json
{
  "count": 1,
  "alerts": [
    {
      "seq_id": 482,
      "event_id": "993b4822-1f4a-4bc3-95ad-98dfec813b19",
      "timestamp": "2026-08-23T18:12:02.592183Z",
      "camera_id": "CAM-01",
      "track_id": "8",
      "incident_id": "INC-20260823-0004",
      "severity": "RESTRICTED",
      "message": "SECURITY ALERT: Track 8 (car) entered restricted zone 'Alpha Restricted Perimeter'",
      "confidence": 0.88,
      "source": "video_file"
    }
  ]
}
```

#### `POST /api/alerts/{event_id}/acknowledge`
**Purpose**: Mark an alert event as acknowledged by a security operator.

- **Response (200 OK)**:
```json
{
  "event_id": "993b4822-1f4a-4bc3-95ad-98dfec813b19",
  "status": "acknowledged"
}
```

#### `GET /api/incidents`
**Purpose**: List aggregated incidents across cameras with event counts and temporal spans.

- **Query Parameters**:
  - `camera_id` (optional, string)
  - `limit` (optional, integer, default: `50`)

- **Response (200 OK)**:
```json
{
  "count": 1,
  "incidents": [
    {
      "incident_id": "INC-20260823-0004",
      "camera_id": "CAM-01",
      "total_events": 4,
      "first_seen": "2026-08-23T18:12:01.200000Z",
      "last_seen": "2026-08-23T18:12:02.592183Z",
      "status": "opened"
    }
  ]
}
```

#### `GET /api/incidents/{incident_id}`
**Purpose**: Retrieve full chronological event timeline for a specific incident.

- **Response (200 OK)**:
```json
{
  "incident_id": "INC-20260823-0004",
  "camera_id": "CAM-01",
  "count": 4,
  "timeline": [
    {
      "seq_id": 480,
      "event_id": "d1283a00-1f4a-4bc3-95ad-98dfec813b10",
      "event_type": "detection",
      "timestamp": "2026-08-23T18:12:01.200000Z",
      "payload": { "class_name": "car", "confidence": 0.89 }
    },
    {
      "seq_id": 481,
      "event_id": "e2394b11-1f4a-4bc3-95ad-98dfec813b11",
      "event_type": "zone",
      "timestamp": "2026-08-23T18:12:02.100000Z",
      "payload": { "zone_name": "Alpha Restricted Perimeter", "transition_type": "entry" }
    },
    {
      "seq_id": 482,
      "event_id": "993b4822-1f4a-4bc3-95ad-98dfec813b19",
      "event_type": "alert",
      "timestamp": "2026-08-23T18:12:02.592183Z",
      "payload": { "severity": "RESTRICTED", "message": "SECURITY ALERT: Track 8 (car) entered restricted zone" }
    }
  ]
}
```

---

### 2.4 Security Zones & Virtual Boundaries Management

#### `GET /api/zones`
**Purpose**: List all active polygon security zones and virtual tripwire boundaries.

- **Response (200 OK)**:
```json
{
  "zones": [
    {
      "zone_id": "ZONE_RESTRICTED_ALPHA",
      "name": "Alpha Restricted Perimeter",
      "polygon": [[200.0, 100.0], [1000.0, 100.0], [1000.0, 650.0], [200.0, 650.0]],
      "severity": "restricted",
      "is_active": true,
      "loitering_threshold_seconds": 1.5
    }
  ],
  "boundaries": [
    {
      "boundary_id": "TRIPWIRE_FENCE_01",
      "name": "North Perimeter Fence Line",
      "pt1": [300.0, 350.0],
      "pt2": [900.0, 350.0],
      "severity": "critical",
      "is_active": true
    }
  ]
}
```

#### `POST /api/zones`
**Purpose**: Dynamically create a new polygon security zone.

- **Request Body**:
```json
{
  "zone_id": "ZONE_SOUTH_POST",
  "name": "South Post Restricted Strip",
  "polygon": [[100.0, 100.0], [600.0, 100.0], [600.0, 500.0], [100.0, 500.0]],
  "severity": "restricted",
  "loitering_threshold_seconds": 2.5,
  "loitering_debounce_seconds": 30.0
}
```

#### `POST /api/zones/boundary`
**Purpose**: Dynamically create a new virtual tripwire boundary.

- **Request Body**:
```json
{
  "boundary_id": "FENCE_SOUTH",
  "name": "South Perimeter Fence",
  "pt1": [150.0, 300.0],
  "pt2": [850.0, 300.0],
  "severity": "critical"
}
```

#### `DELETE /api/zones/{zone_id}`
**Purpose**: Delete a security zone or virtual boundary by ID.

- **Response (200 OK)**:
```json
{
  "zone_id": "ZONE_SOUTH_POST",
  "status": "deleted",
  "type": "zone"
}
```

---

### 2.4 Grounded Intelligence Assistant API

#### `POST /api/intelligence/query`
**Purpose**: Natural language query endpoint backed by verified SQLite evidence and strict refusal guardrails.

- **Request Body**:
```json
{
  "query": "Show recent security alerts for camera CAM-01",
  "camera_id": "CAM-01"
}
```

- **Response (200 OK - Standard 3-Tier Grounded)**:
```json
{
  "query": "Show recent security alerts for camera CAM-01",
  "status": "success",
  "observed_facts": [
    "Alert [RESTRICTED] at 2026-08-23T18:12:02.592183 on Camera 'CAM-01' for Track 8: 'SECURITY ALERT: Track 8 (car) entered restricted zone 'Alpha Restricted Perimeter''",
    "Alert [RESTRICTED] at 2026-08-23T18:12:02.403100 on Camera 'CAM-01' for Track 7: 'SECURITY ALERT: Track 7 (car) entered restricted zone 'Alpha Restricted Perimeter''"
  ],
  "rule_results": [
    "Alert was generated because Track 8 violated configured surveillance threshold/boundary rule.",
    "Alert was generated because Track 7 violated configured surveillance threshold/boundary rule."
  ],
  "interpretation": "Recent alerts were triggered by security boundary crossings and restricted zone entries. Most recent: 'SECURITY ALERT: Track 8 (car) entered restricted zone 'Alpha Restricted Perimeter''.",
  "evidence": {
    "camera_id": "CAM-01",
    "total_alerts": 2,
    "time_range": { "latest": "2026-08-23T18:12:02.592183" }
  },
  "grounding_status": "grounded"
}
```

- **Response (200 OK - Refusal / Guardrail Example)**:
```json
{
  "query": "Identify the suspect's facial identity",
  "status": "refused",
  "observed_facts": [],
  "rule_results": [],
  "interpretation": "REFUSAL: Biometric identification is outside the scope of this surveillance platform. The system operates strictly on camera-local bounding box tracking and spatial boundary rules.",
  "evidence": { "refusal_category": "biometric_identification" },
  "grounding_status": "refused"
}
```

---

### 2.5 System Telemetry & Demo Reset

#### `GET /api/system/metrics`
**Purpose**: Granular, un-averaged telemetry for HUD displays.

- **Response (200 OK)**:
```json
{
  "timestamp": "2026-08-23T18:15:00.123456Z",
  "device": "cpu",
  "gpu_available": false,
  "gpu_device_name": null,
  "memory_usage_mb": 268.4,
  "capture_fps": 30.0,
  "ai_processing_fps": 30.4,
  "display_fps": 60.0,
  "effective_visual_fps": 60.0,
  "inference_latency_ms": 42.1,
  "tracking_latency_ms": 2.4,
  "prediction_latency_ms": 0.2,
  "persistence_latency_ms": 0.4,
  "encoding_latency_ms": 2.8,
  "total_pipeline_latency_ms": 27.4,
  "frame_stride": 2,
  "processed_frames": 240,
  "skipped_frames": 0,
  "predicted_frames": 120,
  "dropped_frames": 0,
  "active_tracks": 9,
  "alerts": 12,
  "telemetry": {
    "total_frames_processed": 240,
    "total_frames_dropped": 0,
    "total_events": 482,
    "total_alerts": 12,
    "distinct_cameras": 1,
    "active_cameras": 1
  }
}
```

#### `POST /api/system/demo-reset`
**Purpose**: Safely reset camera buffers, in-memory pipelines, and demo state before live judge demonstration.

- **Response (200 OK)**:
```json
{
  "status": "reset_complete",
  "timestamp": "2026-08-23T18:15:30.000000Z",
  "active_cameras": 1,
  "message": "Demo state reset successfully. Pipeline is primed for demonstration."
}
```

---

### 2.6 Video Streaming

#### `GET /api/stream/video/{camera_id}`
**Purpose**: Multipart MJPEG video stream for HTML `<img>` tag or Canvas rendering.
- **Content-Type**: `multipart/x-mixed-replace; boundary=frame`
- **Usage**:
```html
<img src="http://127.0.0.1:8000/api/stream/video/CAM-01" alt="Live CCTV" />
```

---

## 3. WebSocket Event Stream (`ws://127.0.0.1:8000/ws/events`)

### 3.1 Connection & Keepalive
- Connect to `ws://127.0.0.1:8000/ws/events`
- Send `{"type": "ping"}` every 30s to maintain keepalive.
- Backend responds with `{"type": "pong"}`.

### 3.2 Event Types & Schemas

#### A. Alert Event (`event_type: "alert"`)
```json
{
  "event_id": "993b4822-1f4a-4bc3-95ad-98dfec813b19",
  "event_type": "alert",
  "timestamp": "2026-08-23T18:12:02.592183Z",
  "camera_id": "CAM-01",
  "track_id": "8",
  "incident_id": "INC-20260823-0004",
  "confidence": 0.88,
  "source": "video_file",
  "severity": "RESTRICTED",
  "message": "SECURITY ALERT: Track 8 (car) entered restricted zone 'Alpha Restricted Perimeter'"
}
```

#### B. Zone Event (`event_type: "zone"`)
```json
{
  "event_id": "e2394b11-1f4a-4bc3-95ad-98dfec813b11",
  "event_type": "zone",
  "timestamp": "2026-08-23T18:12:02.100000Z",
  "camera_id": "CAM-01",
  "track_id": "8",
  "incident_id": "INC-20260823-0004",
  "confidence": 0.88,
  "source": "video_file",
  "zone_id": "ZONE_RESTRICTED_ALPHA",
  "zone_name": "Alpha Restricted Perimeter",
  "transition_type": "entry",
  "dwell_duration_seconds": 0.0
}
```

#### C. Tracking Event (`event_type: "tracking"`)
```json
{
  "event_id": "f3405c22-1f4a-4bc3-95ad-98dfec813b12",
  "event_type": "tracking",
  "timestamp": "2026-08-23T18:12:02.100000Z",
  "camera_id": "CAM-01",
  "track_id": "8",
  "confidence": 0.88,
  "source": "video_file",
  "bounding_box": [320.0, 240.0, 380.0, 310.0],
  "velocity_vector": [1.5, -0.2],
  "speed_pixels_per_sec": 45.2,
  "heading_degrees": 82.4,
  "cardinal_direction": "E",
  "provenance": "detection"
}
```

---

## 4. TypeScript Types Reference (`frontend/src/types/surveillance.ts`)

```typescript
export type CameraStatus = "online" | "offline" | "reconnecting" | "degraded" | "error";
export type AlertSeverity = "info" | "warning" | "restricted" | "critical";
export type EventType = "detection" | "tracking" | "zone" | "alert" | "incident" | "system";
export type ProvenanceType = "detection" | "prediction";

export interface CameraRecord {
  camera_id: string;
  name: string;
  source_type: string;
  location_label: string;
  status: CameraStatus;
  resolution: string;
  native_fps: number;
  fps: number;
  frames_processed: number;
  dropped_frames: number;
  last_seen: string | null;
  is_running: boolean;
}

export interface AlertItem {
  seq_id?: number;
  event_id: string;
  timestamp: string;
  camera_id: string;
  track_id?: string;
  incident_id?: string;
  severity: AlertSeverity;
  message: string;
  confidence?: number;
  source?: string;
}

export interface GroundedIntelligenceResponse {
  query: string;
  status: "success" | "refused" | "error" | "invalid_query";
  observed_facts: string[];
  rule_results: string[];
  interpretation: string;
  evidence: Record<string, any>;
  grounding_status: "grounded" | "refused" | "no_data";
}

export interface SystemMetrics {
  timestamp: string;
  device: string;
  gpu_available: boolean;
  gpu_device_name: string | null;
  memory_usage_mb: number;
  capture_fps: number;
  ai_processing_fps: number;
  display_fps: number;
  effective_visual_fps: number;
  inference_latency_ms: number;
  tracking_latency_ms: number;
  prediction_latency_ms: number;
  persistence_latency_ms: number;
  encoding_latency_ms: number;
  total_pipeline_latency_ms: number;
  frame_stride: number;
  processed_frames: number;
  skipped_frames: number;
  predicted_frames: number;
  dropped_frames: number;
  active_tracks: number;
  alerts: number;
  telemetry: {
    total_frames_processed: number;
    total_frames_dropped: number;
    total_events: number;
    total_alerts: number;
    distinct_cameras: number;
    active_cameras: number;
  };
}

export type ThreatLevel = "DEFCON_GREEN" | "DEFCON_YELLOW" | "DEFCON_ORANGE" | "DEFCON_RED";

export interface ThreatAssessment {
  timestamp: string;
  camera_id: string | null;
  threat_level: ThreatLevel;
  threat_score: number;
  active_breaches: number;
  active_loiterers: number;
  active_tracks: number;
  contributing_factors: string[];
  recommended_action: string;
}

export interface IncidentDossier {
  incident_id: string;
  camera_id: string;
  status: string;
  severity: string;
  first_seen: string;
  last_seen: string;
  duration_seconds: number;
  total_events_logged: number;
  motion_summary?: {
    total_trajectory_points: number;
    net_displacement_pixels: number;
    average_speed_pixels_per_frame: number;
    dominant_heading_degrees?: number;
    dominant_cardinal_direction?: string;
    target_class: string;
  };
  infractions: Array<{
    zone_name: string;
    transition_type: string;
    timestamp: string;
    dwell_duration_seconds?: number;
  }>;
  forensic_hash: string;
  tactical_sitrep: string;
}

export interface CameraDiagnostics {
  camera_id: string;
  status: "OPTIMAL" | "OCCLUDED_OR_BLURRED" | "BLINDED_GLARE" | "LOW_LIGHT_DEGRADED";
  blur_score: number;
  brightness_mean: number;
  glare_percentage: number;
  darkness_percentage: number;
  is_tampered_or_degraded: bool;
  diagnosis_message: string;
}

export interface HeatmapResponse {
  camera_id: string;
  grid_size: number;
  total_points: number;
  max_density: number;
  density_matrix: number[][];
  hotspots_identified: number;
  summary: string;
}
```
