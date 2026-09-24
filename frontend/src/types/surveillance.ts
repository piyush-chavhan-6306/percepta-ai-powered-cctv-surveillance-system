/**
 * Border Intelligence — Core TypeScript Type Definitions
 * Strict single-source-of-truth types matching backend models.
 */

export type CameraStatus = "online" | "offline" | "reconnecting" | "degraded" | "error";
export type AlertSeverity = "info" | "warning" | "restricted" | "critical" | "INFO" | "WARNING" | "RESTRICTED" | "CRITICAL" | string;
export type EventType = "detection" | "tracking" | "zone" | "alert" | "incident" | "system";
export type ProvenanceType = "detection" | "prediction";
export type ThreatLevel = "DEFCON_GREEN" | "DEFCON_YELLOW" | "DEFCON_ORANGE" | "DEFCON_RED";

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
  modality?: string;
  last_error?: string | null;
  codec?: string | null;
  duration_sec?: number | null;
  source_path?: string | null;
  local_video_url?: string;
  custom_zones?: SecurityZone[];
  source_info?: {
    rtsp_url?: string;
    video_path?: string;
  };
}

export interface CameraListResponse {
  count: number;
  cameras: CameraRecord[];
}

export interface CameraDiagnostics {
  camera_id: string;
  status: "OPTIMAL" | "OCCLUDED_OR_BLURRED" | "BLINDED_GLARE" | "LOW_LIGHT_DEGRADED";
  blur_score: number;
  brightness_mean: number;
  glare_percentage: number;
  darkness_percentage: number;
  is_tampered_or_degraded: boolean;
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

export interface AlertItem {
  seq_id?: number;
  event_id: string;
  alert_id?: string;
  timestamp: string;
  camera_id: string;
  track_id?: string;
  incident_id?: string;
  severity: AlertSeverity;
  message: string;
  confidence?: number;
  threat_score?: number;
  threat_level?: string;
  threat_reasons?: string[];
  causal_chain?: any;
  evidence_snapshot_uri?: string;
  evidenceSnapshotUri?: string;
  face_snapshot_uri?: string;
  anpr_snapshot_uri?: string;
  reason?: string;
  heading?: string;
  speed_description?: string;
  object_class?: string;
  targetType?: string;
  plate_number?: string;
  plateNumber?: string;
  source?: string;
  is_acknowledged?: boolean;
}

export interface SimulatedAlert extends Partial<AlertItem> {
  id?: string;
  [key: string]: any;
}


export interface AlertsResponse {
  count: number;
  alerts: AlertItem[];
}

export interface IncidentSummary {
  incident_id: string;
  camera_id: string;
  total_events: number;
  first_seen: string;
  last_seen: string;
  status: string;
  severity?: string;
}

export interface IncidentTimelineEvent {
  seq_id: number;
  event_id: string;
  event_type: string;
  timestamp: string;
  payload: any;
}

export interface IncidentTimelineResponse {
  incident_id: string;
  camera_id: string;
  count: number;
  timeline: IncidentTimelineEvent[];
}

export interface OperatorAnnotation {
  annotation_id: string;
  incident_id: string;
  operator_callsign: string;
  note: string;
  disposition: string;
  timestamp: string;
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

export interface SecurityZone {
  zone_id: string;
  name: string;
  polygon: number[][];
  severity: string;
  is_active: boolean;
  loitering_threshold_seconds?: number | null;
}

export interface VirtualBoundary {
  boundary_id: string;
  name: string;
  pt1: [number, number];
  pt2: [number, number];
  severity: string;
  direction?: string;
  is_active: boolean;
}

export interface ZonesListResponse {
  zones: SecurityZone[];
  boundaries: VirtualBoundary[];
}

export interface ZoneTemplate {
  template_id: string;
  name: string;
  description: string;
  zone_type: string;
  severity: string;
  default_loitering_threshold_seconds?: number | null;
  default_coordinates: any;
}

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

export interface ForensicVerificationResult {
  event_id: string;
  seq_id: number;
  timestamp: string;
  camera_id: string;
  event_type: string;
  computed_sha256_hash: string;
  tamper_status: "VERIFIED_AUTHENTIC" | "CORRUPTED_OR_TAMPERED";
  is_authentic: boolean;
  verification_timestamp: string;
}

export interface EvidenceVerificationResult {
  evidence_id: string;
  incident_id?: string;
  camera_id?: string;
  evidence_type: string;
  stored_hash?: string;
  computed_hash?: string;
  file_path?: string;
  file_exists: boolean;
  file_bytes_checked: number;
  verification_status: "VERIFIED" | "COMPROMISED" | "MISSING" | "INVALID" | "VERIFICATION_ERROR";
  audit_verdict: string;
  verified_at: string;
}

export interface IntegrityAuditReport {
  audit_timestamp: string;
  total_records_checked: number;
  authentic_count: number;
  tampered_count: number;
  root_chain_hash: string;
  audit_verdict: "PASS_INTEGRITY_VERIFIED" | "FAIL_TAMPERING_DETECTED";
}

export interface SnapshotMetadata {
  snapshot_id: string;
  incident_id: string;
  camera_id: string;
  frame_number: number;
  trigger_reason: string;
  file_path: string;
  file_uri: string;
  timestamp: string;
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

export interface CoverageReport {
  report_timestamp: string;
  total_cameras_registered: number;
  active_cameras_online: number;
  sector_coverage_percentage: number;
  surveillance_readiness_grade: "GRADE_A_COMBAT_READY" | "GRADE_B_DEGRADED" | "GRADE_C_VULNERABLE";
  strategic_assessment: string;
  total_events_logged: number;
  total_alerts_logged: number;
  camera_fleet_status: Array<{
    camera_id: string;
    name: string;
    status: string;
    fps: number;
    frames_processed: number;
    dropped_frames: number;
  }>;
}

export interface OperationalProfile {
  profile_id: string;
  name: string;
  description: string;
  confidence_threshold: number;
  iou_threshold: number;
  frame_stride: number;
  loitering_threshold_seconds: number;
  optical_mode: string;
}

export interface DatabaseDiagnostics {
  engine: string;
  journal_mode: string;
  synchronous_level: number;
  page_size_bytes: number;
  total_pages: number;
  db_file_size_mb: number;
  wal_file_size_mb: number;
  total_storage_mb: number;
  health_probe_latency_ms: number;
  wal_health_status: string;
  enterprise_migration: {
    status: string;
    orm_layer: string;
    dialect_locks: string;
    migration_complexity: string;
  };
}

export interface AuditLogEntry {
  audit_id: string;
  action: string;
  actor: string;
  details: Record<string, any>;
  timestamp: string;
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

export interface MultiModalSensorsStatus {
  total_sensors: number;
  sensors: Record<string, {
    type: string;
    sector: string;
    status: string;
    last_seen?: string;
  }>;
}
