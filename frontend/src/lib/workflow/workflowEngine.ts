/**
 * Workflow / Rule Engine.
 *
 * Evaluates a normalized SurveillanceEvent and executes the
 * matching rule: creates an alert (and optionally an incident).
 *
 * This module is completely source-independent.
 * It receives events — it does not care if they came from a demo
 * video, RTSP stream, or live camera.
 *
 * To add a new rule:
 *   1. Add the EventType to eventTypes.ts
 *   2. Add a case here and return the appropriate alert/incident.
 */
import type {
  SurveillanceEvent,
  SurveillanceAlert,
  Incident,
  AlertSeverity,
} from "../events/eventTypes";

let _alertCount  = 0;
let _incidentCount = 0;

export interface WorkflowResult {
  alert: SurveillanceAlert | null;
  incident: Incident | null;
  /** Human-readable trace of the executed workflow steps. */
  trace: string;
}

export function resetCounters(): void {
  _alertCount    = 0;
  _incidentCount = 0;
}

function uid(prefix: string, n: number): string {
  return `${prefix}-${String(n).padStart(4, "0")}`;
}

function buildAlert(
  event: SurveillanceEvent,
  severity: AlertSeverity,
  title: string,
): SurveillanceAlert {
  return {
    id:        uid("ALT", ++_alertCount),
    eventId:   event.id,
    severity,
    title,
    cameraId:  event.cameraId,
    timestamp: event.timestamp,
    status:    "NEW",
    source:    event.source,
  };
}

function buildIncident(
  event: SurveillanceEvent,
  alert: SurveillanceAlert,
): Incident {
  return {
    id:          uid("INC", ++_incidentCount),
    alertId:     alert.id,
    type:        event.type,
    description: `Automated security incident. ${event.description} — Camera: ${event.cameraId}`,
    cameraId:    event.cameraId,
    timestamp:   event.timestamp,
    status:      "NEW",
  };
}

/**
 * Evaluate an event and execute the matching workflow rule.
 *
 * Rules (in order of severity):
 *   ZONE_INTRUSION   → CRITICAL alert + Security Incident created
 *   PERSON_DETECTED  → WARNING alert
 *   VEHICLE_DETECTED → WARNING alert
 *   MOVEMENT_DETECTED→ INFO only (event logged, no escalation)
 */
export function evaluateEvent(event: SurveillanceEvent): WorkflowResult {
  switch (event.type) {
    case "ZONE_INTRUSION": {
      const alert    = buildAlert(event, "CRITICAL", "ZONE INTRUSION DETECTED");
      const incident = buildIncident(event, alert);
      return {
        alert, incident,
        trace: `${event.type} → RULE MATCH [zone-intrusion] → SECURITY INCIDENT ${incident.id} → 🚨 ${alert.id} GENERATED → EVENT LOGGED`,
      };
    }
    case "PERSON_DETECTED": {
      const alert = buildAlert(event, "WARNING", "PERSON DETECTED");
      return {
        alert, incident: null,
        trace: `${event.type} → RULE MATCH [person-watch] → ⚠ ${alert.id} GENERATED → EVENT LOGGED`,
      };
    }
    case "VEHICLE_DETECTED": {
      const alert = buildAlert(event, "WARNING", "VEHICLE DETECTED");
      return {
        alert, incident: null,
        trace: `${event.type} → RULE MATCH [vehicle-watch] → ⚠ ${alert.id} GENERATED → EVENT LOGGED`,
      };
    }
    case "MOVEMENT_DETECTED": {
      return {
        alert: null, incident: null,
        trace: `${event.type} → RULE MATCH [motion-log] → EVENT LOGGED (no escalation)`,
      };
    }
    default:
      return { alert: null, incident: null, trace: "No matching rule." };
  }
}
