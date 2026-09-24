/**
 * PERCEPTA — Realistic Demo Data Generator
 * Provides simulated surveillance data that makes the UI functional
 * without a running backend. Structured so all data can be swapped
 * for real API responses later.
 */

import type {
  CameraRecord,
  AlertItem,
  IncidentSummary,
  ThreatAssessment,
  SystemMetrics,
  CoverageReport,
  SecurityZone,
  VirtualBoundary,
} from "../types/surveillance";

export type {
  CameraRecord,
  AlertItem,
  IncidentSummary,
  ThreatAssessment,
  SystemMetrics,
  CoverageReport,
  SecurityZone,
  VirtualBoundary,
};

// ─── Utility ────────────────────────────────────────────────────────────────
const now = new Date();
const ago = (sec: number) => new Date(now.getTime() - sec * 1000).toISOString();
const pick = <T>(arr: T[]): T => arr[Math.floor(Math.random() * arr.length)];
const rand = (min: number, max: number) => Math.random() * (max - min) + min;
const randInt = (min: number, max: number) => Math.floor(rand(min, max));

// ─── Camera Fleet ───────────────────────────────────────────────────────────
export const DEMO_CAMERAS: CameraRecord[] = [
  {
    camera_id: "CAM-01",
    name: "North Gate Sentinel",
    source_type: "bundled_video",
    location_label: "Sector Alpha — North Perimeter",
    status: "online",
    resolution: "1920x1080",
    native_fps: 30,
    fps: 30,
    frames_processed: 1_247_382,
    dropped_frames: 12,
    last_seen: ago(1),
    is_running: true,
  },
  {
    camera_id: "CAM-02",
    name: "East Watch Tower",
    source_type: "bundled_video",
    location_label: "Sector Bravo — Eastern Boundary",
    status: "online",
    resolution: "1920x1080",
    native_fps: 25,
    fps: 25,
    frames_processed: 982_104,
    dropped_frames: 3,
    last_seen: ago(2),
    is_running: true,
  },
  {
    camera_id: "CAM-03",
    name: "South Checkpoint",
    source_type: "bundled_video",
    location_label: "Sector Charlie — Southern Approach",
    status: "online",
    resolution: "1280x720",
    native_fps: 24,
    fps: 24,
    frames_processed: 856_991,
    dropped_frames: 7,
    last_seen: ago(1),
    is_running: true,
  },
  {
    camera_id: "CAM-04",
    name: "West Perimeter Patrol",
    source_type: "bundled_video",
    location_label: "Sector Delta — Western Fence Line",
    status: "offline",
    resolution: "1920x1080",
    native_fps: 30,
    fps: 0,
    frames_processed: 432_100,
    dropped_frames: 89,
    last_seen: ago(3600),
    is_running: false,
  },
  {
    camera_id: "CAM-05",
    name: "Interior Corridor 7",
    source_type: "webcam",
    location_label: "Building Interior — Corridor 7B",
    status: "online",
    resolution: "1280x720",
    native_fps: 30,
    fps: 30,
    frames_processed: 2_104_388,
    dropped_frames: 0,
    last_seen: ago(1),
    is_running: true,
  },
  {
    camera_id: "CAM-06",
    name: "Perimeter Thermal A",
    source_type: "bundled_video",
    location_label: "Sector Alpha — Thermal Array",
    status: "online",
    resolution: "640x480",
    native_fps: 15,
    fps: 15,
    frames_processed: 512_300,
    dropped_frames: 1,
    last_seen: ago(3),
    is_running: true,
  },
];

// ─── Detection Boxes (simulated per-frame data) ─────────────────────────────
export interface DetectionBox {
  trackId: string;
  label: "person" | "vehicle" | "animal" | "unknown";
  confidence: number;
  conf?: number;
  x: number; // percentage
  y: number;
  w: number;
  h: number;
  color: string;
}

const TRACK_COLORS = ["#ff1744", "#00e676", "#2979ff", "#ffab00", "#e040fb", "#00e5ff"];

export function generateDetectionBoxes(cameraId: string, count = 4): DetectionBox[] {
  const boxes: DetectionBox[] = [];
  const trackNum = parseInt(cameraId.replace(/\D/g, "")) || 1;
  for (let i = 0; i < count; i++) {
    const label = pick(["person", "person", "vehicle", "person"] as const);
    boxes.push({
      trackId: `T-${trackNum}${String(i + 1).padStart(2, "0")}`,
      label,
      confidence: parseFloat(rand(0.72, 0.99).toFixed(2)),
      x: rand(5, 80),
      y: rand(20, 70),
      w: label === "vehicle" ? rand(8, 16) : rand(3, 7),
      h: label === "vehicle" ? rand(5, 10) : rand(8, 18),
      color: TRACK_COLORS[i % TRACK_COLORS.length],
    });
  }
  return boxes;
}

// ─── Alert Stream ────────────────────────────────────────────────────────────
export interface DemoAlert {
  id: string;
  timestamp: string;
  cameraId: string;
  trackId: string;
  severity: "critical" | "restricted" | "warning" | "info";
  message: string;
  confidence: number;
  acknowledged: boolean;
}

const ALERT_TEMPLATES = [
  { severity: "critical" as const, message: "Unauthorized perimeter breach detected — Sector Alpha fence line", confidence: 0.96 },
  { severity: "critical" as const, message: "Intrusion alert: Person breached restricted zone perimeter", confidence: 0.94 },
  { severity: "restricted" as const, message: "Loitering detected near restricted area — dwell time exceeding threshold", confidence: 0.88 },
  { severity: "restricted" as const, message: "Zone boundary crossed — multiple track targets in no-go area", confidence: 0.91 },
  { severity: "warning" as const, message: "Suspicious vehicle movement pattern near checkpoint approach", confidence: 0.82 },
  { severity: "warning" as const, message: "Rapid approach trajectory detected — closing distance at 4.2 m/s", confidence: 0.79 },
  { severity: "info" as const, message: "New track assigned — person entering monitored perimeter from east", confidence: 0.95 },
  { severity: "info" as const, message: "Camera diagnostics: blur score elevated — possible obstruction", confidence: 0.65 },
  { severity: "restricted" as const, message: "Multiple persons detected in restricted buffer zone — alerting operators", confidence: 0.87 },
  { severity: "warning" as const, message: "Vehicle stopped outside authorized parking — exceeds 120s threshold", confidence: 0.83 },
];

export const DEMO_ALERTS: DemoAlert[] = ALERT_TEMPLATES.map((tpl, i) => ({
  id: `ALT-${String(1000 + i).padStart(6, "0")}`,
  timestamp: ago(randInt(5, 3600)),
  cameraId: DEMO_CAMERAS[i % DEMO_CAMERAS.length].camera_id,
  trackId: `T-${randInt(1, 9)}${String(randInt(1, 20)).padStart(2, "0")}`,
  ...tpl,
  acknowledged: i > 6,
}));

// ─── Incidents ───────────────────────────────────────────────────────────────
export interface DemoIncident {
  id: string;
  cameraId: string;
  severity: "critical" | "restricted" | "warning";
  status: "ACTIVE" | "ACKNOWLEDGED" | "RESOLVED";
  firstSeen: string;
  lastSeen: string;
  totalEvents: number;
  threatScore: number;
  description: string;
  factors: string[];
  timeline: Array<{
    time: string;
    event: string;
    type: "detection" | "alert" | "tracking" | "zone";
  }>;
}

export const DEMO_INCIDENTS: DemoIncident[] = [
  {
    id: "INC-00001",
    cameraId: "CAM-01",
    severity: "critical",
    status: "ACTIVE",
    firstSeen: ago(180),
    lastSeen: ago(5),
    totalEvents: 14,
    threatScore: 87,
    description: "Multiple unauthorized personnel breached north perimeter fence line. Primary target tracked through restricted corridor.",
    factors: ["Zone breach", "Multiple tracks", "High confidence", "Sustained presence"],
    timeline: [
      { time: ago(180), event: "Person detected approaching fence line", type: "detection" },
      { time: ago(165), event: "Track T-0103 assigned — person, 94% confidence", type: "tracking" },
      { time: ago(150), event: "Zone boundary crossing detected", type: "zone" },
      { time: ago(120), event: "RESTRICTED severity alert generated", type: "alert" },
      { time: ago(90), event: "Second track T-0104 detected following primary", type: "detection" },
      { time: ago(60), event: "Both tracks deep inside restricted corridor", type: "zone" },
      { time: ago(30), event: "Escalated to CRITICAL — sustained intrusion", type: "alert" },
      { time: ago(5), event: "Latest position update — still in restricted zone", type: "tracking" },
    ],
  },
  {
    id: "INC-00002",
    cameraId: "CAM-02",
    severity: "restricted",
    status: "ACTIVE",
    firstSeen: ago(420),
    lastSeen: ago(30),
    totalEvents: 8,
    threatScore: 62,
    description: "Vehicle detected loitering near eastern boundary approach. Pattern consistent with reconnaissance behavior.",
    factors: ["Loitering >120s", "Vehicle track", "Boundary proximity"],
    timeline: [
      { time: ago(420), event: "Vehicle detected entering monitored perimeter", type: "detection" },
      { time: ago(380), event: "Track T-0201 assigned — vehicle, 89% confidence", type: "tracking" },
      { time: ago(300), event: "Vehicle stopped — loitering timer started", type: "zone" },
      { time: ago(180), event: "Loitering threshold exceeded — 120s", type: "alert" },
      { time: ago(120), event: "RESTRICTED alert: sustained unauthorized presence", type: "alert" },
      { time: ago(30), event: "Vehicle resumed movement — pattern logged", type: "tracking" },
    ],
  },
  {
    id: "INC-00003",
    cameraId: "CAM-05",
    severity: "warning",
    status: "ACKNOWLEDGED",
    firstSeen: ago(900),
    lastSeen: ago(600),
    totalEvents: 5,
    threatScore: 41,
    description: "Person detected in building interior corridor outside authorized hours. Likely false alarm — cleaning staff.",
    factors: ["After-hours detection", "Interior zone", "Single track", "Acknowledged by operator"],
    timeline: [
      { time: ago(900), event: "Motion detected in Corridor 7B", type: "detection" },
      { time: ago(870), event: "Track T-0501 assigned — person, 91% confidence", type: "tracking" },
      { time: ago(840), event: "WARNING alert generated — after-hours presence", type: "alert" },
      { time: ago(720), event: "Operator acknowledged — classified as false alarm", type: "alert" },
      { time: ago(600), event: "Track exited monitored zone — incident resolved", type: "tracking" },
    ],
  },
  {
    id: "INC-00004",
    cameraId: "CAM-03",
    severity: "restricted",
    status: "RESOLVED",
    firstSeen: ago(1800),
    lastSeen: ago(1500),
    totalEvents: 10,
    threatScore: 55,
    description: "Group of three persons approached southern checkpoint without credentials. Verified as authorized maintenance crew.",
    factors: ["Multiple tracks", "Checkpoint approach", "No credentials", "Resolved — authorized"],
    timeline: [
      { time: ago(1800), event: "Three persons detected approaching checkpoint", type: "detection" },
      { time: ago(1770), event: "Tracks T-0301 through T-0303 assigned", type: "tracking" },
      { time: ago(1740), event: "RESTRICTED alert — unauthorized group approach", type: "alert" },
      { time: ago(1650), event: "Group stopped at checkpoint — visual confirmation", type: "tracking" },
      { time: ago(1500), event: "Operator verified as maintenance crew — RESOLVED", type: "alert" },
    ],
  },
];

// ─── Threat Assessment ──────────────────────────────────────────────────────
export const DEMO_THREAT: ThreatAssessment = {
  timestamp: ago(2),
  camera_id: null,
  threat_level: "DEFCON_ORANGE",
  threat_score: 68,
  active_breaches: 2,
  active_loiterers: 1,
  active_tracks: 7,
  contributing_factors: [
    "Active perimeter breach — Sector Alpha",
    "Loitering vehicle — Sector Bravo",
    "Multiple unauthorized tracks in restricted zones",
    "Elevated activity across 3 camera sectors",
  ],
  recommended_action: "Elevate to DEFCON_RED if breaches persist beyond 5 minutes. Deploy rapid response to Sector Alpha.",
};

// ─── System Metrics ─────────────────────────────────────────────────────────
export const DEMO_METRICS: SystemMetrics = {
  timestamp: ago(1),
  device: "NVIDIA GeForce RTX 3060",
  gpu_available: true,
  gpu_device_name: "NVIDIA GeForce RTX 3060",
  memory_usage_mb: 1842,
  capture_fps: 28.4,
  ai_processing_fps: 26.8,
  display_fps: 30,
  effective_visual_fps: 26.8,
  inference_latency_ms: 23.4,
  tracking_latency_ms: 8.2,
  prediction_latency_ms: 3.1,
  persistence_latency_ms: 4.7,
  encoding_latency_ms: 6.8,
  total_pipeline_latency_ms: 46.2,
  frame_stride: 1,
  processed_frames: 6_134_265,
  skipped_frames: 142,
  predicted_frames: 23_100,
  dropped_frames: 112,
  active_tracks: 7,
  alerts: 3,
  telemetry: {
    total_frames_processed: 6_134_265,
    total_frames_dropped: 112,
    total_events: 14_382,
    total_alerts: 487,
    distinct_cameras: 6,
    active_cameras: 5,
  },
};

// ─── Coverage Report ────────────────────────────────────────────────────────
export const DEMO_COVERAGE: CoverageReport = {
  report_timestamp: ago(3),
  total_cameras_registered: 6,
  active_cameras_online: 5,
  sector_coverage_percentage: 83,
  surveillance_readiness_grade: "GRADE_A_COMBAT_READY",
  strategic_assessment: "All primary sectors monitored. One camera offline in Sector Delta — maintenance required. Overall perimeter integrity at 83%.",
  total_events_logged: 14_382,
  total_alerts_logged: 487,
  camera_fleet_status: DEMO_CAMERAS.map((c) => ({
    camera_id: c.camera_id,
    name: c.name,
    status: c.status,
    fps: c.fps,
    frames_processed: c.frames_processed,
    dropped_frames: c.dropped_frames,
  })),
};

// ─── Security Zones ─────────────────────────────────────────────────────────
export const DEMO_ZONES: SecurityZone[] = [
  {
    zone_id: "zone-alpha-01",
    name: "Restricted Zone Alpha",
    polygon: [[120, 80], [320, 80], [340, 280], [100, 260]],
    severity: "critical",
    is_active: true,
    loitering_threshold_seconds: 30,
  },
  {
    zone_id: "zone-bravo-01",
    name: "Monitoring Zone Bravo",
    polygon: [[50, 300], [250, 300], [280, 400], [30, 380]],
    severity: "warning",
    is_active: true,
    loitering_threshold_seconds: 120,
  },
  {
    zone_id: "zone-charlie-01",
    name: "Buffer Zone Charlie",
    polygon: [[300, 100], [450, 100], [460, 250], [290, 240]],
    severity: "info",
    is_active: true,
  },
];

export const DEMO_BOUNDARIES: VirtualBoundary[] = [
  {
    boundary_id: "tripwire-north-01",
    name: "North Tripwire",
    pt1: [50, 320],
    pt2: [350, 300],
    severity: "critical",
    is_active: true,
  },
  {
    boundary_id: "tripwire-east-01",
    name: "East Approach Line",
    pt1: [380, 50],
    pt2: [380, 350],
    severity: "warning",
    is_active: true,
  },
];

// ─── Derived Helpers ─────────────────────────────────────────────────────────
export function getSeverityColor(severity: string): string {
  switch (severity?.toUpperCase()) {
    case "CRITICAL":
    case "DEFCON_RED":
      return "#ff1744";
    case "RESTRICTED":
    case "DEFCON_ORANGE":
      return "#ff6d00";
    case "WARNING":
    case "DEFCON_YELLOW":
      return "#ffab00";
    case "INFO":
    case "DEFCON_GREEN":
      return "#00e676";
    default:
      return "#64748b";
  }
}

export function getSeverityBg(severity: string): string {
  switch (severity?.toUpperCase()) {
    case "CRITICAL":
      return "rgba(255,23,68,0.15)";
    case "RESTRICTED":
      return "rgba(255,109,0,0.15)";
    case "WARNING":
      return "rgba(255,171,0,0.12)";
    case "INFO":
      return "rgba(0,230,118,0.12)";
    default:
      return "rgba(100,116,139,0.1)";
  }
}

export function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString("en-US", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function formatRelativeTime(iso: string): string {
  const diff = Math.floor((now.getTime() - new Date(iso).getTime()) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}
