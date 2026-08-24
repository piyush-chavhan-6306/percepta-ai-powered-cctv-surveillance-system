/**
 * Demo scenario configuration.
 *
 * Edit the `time` values below to match your video content.
 * The simulation engine fires each event exactly once when
 * video.currentTime >= event.time.
 *
 * This file is the ONLY place you need to touch to change
 * what happens during a demo run.
 */
import type { EventType } from "../events/eventTypes";

export interface ScenarioEvent {
  time: number;          // seconds into the video
  type: EventType;
  description: string;
  confidence?: number;   // 0-1, omit for purely simulated events
}

/** Change these timestamps and descriptions to match your demo video. */
export const DEMO_SCENARIO: ScenarioEvent[] = [
  {
    time: 4,
    type: "MOVEMENT_DETECTED",
    description: "Motion detected in Sector Alpha perimeter — camera triggered",
    confidence: 0.88,
  },
  {
    time: 8,
    type: "PERSON_DETECTED",
    description: "Unidentified individual approaching fence line",
    confidence: 0.91,
  },
  {
    time: 13,
    type: "VEHICLE_DETECTED",
    description: "Unknown vehicle detected on restricted access road",
    confidence: 0.85,
  },
  {
    time: 18,
    type: "ZONE_INTRUSION",
    description: "ALERT: Individual crossed restricted zone boundary",
    confidence: 0.96,
  },
  {
    time: 24,
    type: "PERSON_DETECTED",
    description: "Second individual moving toward sector boundary",
    confidence: 0.79,
  },
  {
    time: 30,
    type: "ZONE_INTRUSION",
    description: "CRITICAL: Multiple persons confirmed inside restricted zone",
    confidence: 0.98,
  },
];

export const DEMO_CAMERA_ID   = "CAM-01";
export const DEMO_LOCATION    = "SECTOR A — BORDER PERIMETER";
export const DEMO_VIDEO_PATH  = "/videos/border-demo.mp4";
