# BORDER INTELLIGENCE — FRONTEND GAP AUDIT & ARCHITECTURE PLAN

**Project**: Border Intelligence — AI-Powered Persistent Border Surveillance & Incident Intelligence Platform  
**SIH Problem Statement**: PS SIH26187 ("AI-Based Intelligent Video Analytics Platform for Border Surveillance using existing CCTV Infrastructure")  
**Audit Date**: August 24, 2026  
**Backend Baseline**: 🟢 **130 / 130 Automated Tests Passing (FROZEN)**  
**Status**: 🟢 **PHASE 1 COMPLETE — READY FOR FRONTEND IMPLEMENTATION**

---

## 1. Existing State Assessment

- **Existing Frontend Directory**: None (`frontend/` directory does not yet exist in the root repository).
- **Backend API Readiness**: 100% complete across 47 REST & WebSocket endpoints covering Tier-S, Tier-A, and Tier-B capabilities.
- **Contract Source of Truth**: [`BACKEND_FRONTEND_CONTRACT.md`](file:///d:/SIH%20%20%20border%20cctv/BACKEND_FRONTEND_CONTRACT.md) and [`EXHAUSTIVE_BACKEND_VERIFICATION_REPORT.md`](file:///d:/SIH%20%20%20border%20cctv/EXHAUSTIVE_BACKEND_VERIFICATION_REPORT.md).

---

## 2. Categorized Frontend Findings & Requirements

### P0 — Blocking (Core UI Foundation & Communication)
1. **Frontend Project Initialization**: Initialize a high-performance React + TypeScript SPA with Vite in `frontend/`.
2. **Type Definitions**: Comprehensive TypeScript contracts in `src/types/surveillance.ts` matching all backend models.
3. **REST API Client**: Unified HTTP client (`src/api/client.ts`) connecting to `http://127.0.0.1:8000` with typed methods, retry handling, and error boundaries.
4. **WebSocket Real-Time Engine**: Persistent WebSocket manager (`src/hooks/useWebSocket.ts`) connecting to `ws://127.0.0.1:8000/ws/events` with auto-reconnect, exponential backoff, ping/pong keepalive, and event deduplication.
5. **State Management**: Centralized reactive state store (`src/store/surveillanceStore.ts`) aggregating cameras, live alerts, incidents, system metrics, threat level, and connection status.
6. **Command Center Navigation Shell**: Top-level tactical command navigation header, status ticker, DEFCON indicator, and view router.

---

### P1 — Important (Command Center Operational Views)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                               8 COMMAND CENTER VIEWS                                    │
├─────────────────────────────────────────────────────────────────────────────────────────┤
│ 1. DASHBOARD:        Threat level, active alerts, incidents, camera readiness, FPS HUD  │
│ 2. SURVEILLANCE:     Multi-camera grid, MJPEG stream, optical diagnostics, PTZ controls │
│ 3. INCIDENTS:        Aggregated incidents, timeline, SitRep dossier, operator notes     │
│ 4. ZONES:            Polygon zones, virtual tripwires, tactical templates deployment    │
│ 5. THREAT INTEL:     DEFCON score matrix, contributing factors, 16x16 spatial heatmap   │
│ 6. EVIDENCE:         SHA-256 forensics, chain of custody audit, snapshot browser, export│
│ 7. SENSORS & SYSTEM: Radar, seismic, thermal IR, DB WAL diagnostics, coverage report   │
│ 8. AI INTELLIGENCE:  3-Tier grounded Q&A (Observed Fact, Deterministic Rule, AI Summary)│
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

1. **View 1: Dashboard (`src/views/DashboardView.tsx`)**:
   - High-visibility DEFCON Threat HUD with colored badges (`DEFCON_GREEN`, `DEFCON_YELLOW`, `DEFCON_ORANGE`, `DEFCON_RED`).
   - Sector Fleet Coverage & Readiness grade (`GRADE_A_COMBAT_READY`, `GRADE_B_DEGRADED`).
   - Real-time alert ticker with 1-click acknowledgment.
   - Hardware & inference telemetry (Inference latency, pipeline FPS, capture FPS).
2. **View 2: Live Surveillance (`src/views/SurveillanceView.tsx`)**:
   - Responsive multi-camera video feed grid supporting 1, 2, 4, or 6 cameras.
   - Decoupled MJPEG stream rendering (`/api/stream/video/{camera_id}`) with fallback indicators.
   - Optical diagnostics indicator (Optimal, Occluded/Blurred, Blinded/Glare, Low Light).
   - Camera registration modal (RTSP with password masking, video file, simulation).
   - Camera start, stop, and reconnect controls.
3. **View 3: Incident Command (`src/views/IncidentsView.tsx`)**:
   - Incident master-detail view with severity filters (`CRITICAL`, `RESTRICTED`, `WARNING`, `INFO`).
   - Chronological event timeline modal.
   - One-click Tactical Incident Dossier / SitRep generator with motion vectors and SHA-256 tokens.
   - Duty Officer Annotation Log: Append operator notes and QRF dispatch dispositions.
   - Visual snapshot evidence viewer.
4. **View 4: Security Zones & Boundaries (`src/views/ZonesView.tsx`)**:
   - Active polygon zones and virtual tripwire boundaries list.
   - Tactical Defense Templates library (`BORDER_RESTRICTED_STRIP`, `GATE_ACCESS_FUNNEL`, `CRITICAL_INFRASTRUCTURE_BOX`, `VIRTUAL_PERIMETER_FENCE`).
   - Fast one-click template applicator.
   - Custom polygon zone and tripwire creation forms.
5. **View 5: Threat Intelligence (`src/views/ThreatView.tsx`)**:
   - Real-time DEFCON score dial (0 - 100) and contributing threat factors.
   - Actionable tactical recommendations for command post operators.
   - $16 \times 16$ normalized 2D spatial breach heatmap density matrix with hotspot detection.
6. **View 6: Evidence & Forensics (`src/views/ForensicsView.tsx`)**:
   - Cryptographic SHA-256 verification tool for event tokens (`GET /api/evidence/verify/{id}`).
   - SQLite WAL database chain-of-custody audit report.
   - Visual JPEG Snapshot Evidence Archive browser.
   - Multi-criteria forensic export in structured JSON or CSV format.
7. **View 7: Sensors & System Health (`src/views/SensorsSystemView.tsx`)**:
   - Multi-Modal Defense Sensors panel (Radar tracks, Ground Seismic vibrations, Thermal IR signatures, RF triggers) with live telemetry simulator.
   - SQLite WAL database storage health & PostgreSQL migration readiness report.
   - Fleet-wide camera coverage and uptime analytics report.
   - Environmental Surveillance Sensitivity Profiles switcher (`STANDARD_DAY`, `HIGH_SENSITIVITY_NIGHT`, `ADVERSE_WEATHER_STORM`, `HIGH_TRAFFIC_CONVOY`).
8. **View 8: Grounded AI Intelligence (`src/views/IntelligenceView.tsx`)**:
   - Operator natural-language surveillance query interface.
   - Strict 3-tier response display cleanly separating:
     - `[OBSERVED FACT]`
     - `[DETERMINISTIC RULE RESULT]`
     - `[AI INTERPRETATION / SUMMARY]`
   - Anti-hallucination refusal banner for out-of-scope/biometric/speculative queries.

---

### P2 — Polish (UX & Defense Ergonomics)
- Dark tactical theme (zinc/slate color palette with amber/emerald/crimson accents).
- Audio alert chime toggle with visual badge pulsing.
- Demo reset button (`POST /api/system/demo-reset`) for seamless evaluator demonstrations.
- Responsive layout adapting to multi-monitor command workstations.

---

### P3 — Future
- Map-based GIS multi-sector overlay (future tactical extension).

---

## 3. Implementation Plan & Milestones

1. **Step 1**: Scaffold Vite React TypeScript project in `frontend/` and install dependencies (`lucide-react`, `clsx`, `tailwind-merge`).
2. **Step 2**: Create TypeScript schemas in `src/types/surveillance.ts`.
3. **Step 3**: Implement API client in `src/api/client.ts`.
4. **Step 4**: Implement WebSocket hook in `src/hooks/useWebSocket.ts`.
5. **Step 5**: Implement State Store in `src/store/surveillanceContext.tsx`.
6. **Step 6**: Build 8 Command Center Views and modular components.
7. **Step 7**: Build App Layout and View Router.
8. **Step 8**: Validate with tests, build check, and live E2E demo against the running backend.
9. **Step 9**: Document in `FRONTEND_FINAL_VERIFICATION.md`.
