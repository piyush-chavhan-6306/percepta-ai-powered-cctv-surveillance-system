# BORDER INTELLIGENCE — COMMAND CENTER UI ARCHITECTURE

**Project**: Border Intelligence — AI Border Surveillance Command Post (PS SIH26187)  
**Frontend Framework**: React 19 + TypeScript + Vite 8  
**3D Engine**: Three.js (WebGL Hardware Accelerated)  
**Real-Time Protocol**: Auto-Reconnecting WebSocket (`ws://127.0.0.1:8000/ws/events`)  

---

## 1. High-Level Component Hierarchy

```
App.tsx (Root Container, ErrorBoundary, Theme Shell)
  ├── Header.tsx (DEFCON Badge, AI FPS HUD, Fleet Grade, Demo Reset, UTC Clock)
  ├── Navigation.tsx (Categorized Command Post Tabs: MISSION / OPERATIONS / INTELLIGENCE)
  └── View Router (Dynamic View Mount)
        ├── DashboardView.tsx (Primary Tactical HUD)
        │     ├── TacticalMap3D.tsx (Three.js Spatial Situation Map)
        │     ├── ThreatGauge.tsx (Circular DEFCON Dial)
        │     ├── CameraCard.tsx (Featured Video Stream Player & Optics)
        │     └── AlertTicker.tsx (Real-Time 1-Click Acknowledge Stream)
        │
        ├── SurveillanceView.tsx (Multi-Camera Video Wall: 1x1, 2x2, 3x3)
        │     ├── CameraCard.tsx (MJPEG Stream & Lens Diagnostics Modal)
        │     └── Camera Registration Modal (RTSP with Password Sanitization)
        │
        ├── IncidentsView.tsx (Incident Command & SitRep Dossiers)
        │     ├── DossierModal.tsx (Tactical SitRep Generator & JSON Export)
        │     ├── SnapshotModal.tsx (Full-Resolution Visual Evidence Viewer)
        │     └── QRF Escalation & Operator Annotation Logger
        │
        ├── ZonesView.tsx (Polygon Perimeter & Virtual Tripwires Editor)
        │     └── Tactical Defense Templates Preset Applicator
        │
        ├── ThreatView.tsx (Strategic Threat Matrix & 16x16 Heatmap Explorer)
        │     ├── ThreatGauge.tsx (Radial Telemetry & Contributing Factor Bars)
        │     └── 16x16 Interactive Spatial Density Heatmap Grid
        │
        ├── ForensicsView.tsx (Evidence Vault & Chain-of-Custody Verifier)
        │     ├── Cryptographic SHA-256 Token Inspector
        │     ├── SQLite WAL Database Integrity Auditor
        │     └── RFC 4180 CSV / JSON Exporter
        │
        ├── SensorsSystemView.tsx (Defense Multi-Modal Sensors & SQLite Diagnostics)
        │     ├── Multi-Modal Telemetry Simulator (Radar, Seismic, Thermal, RF)
        │     ├── Database WAL Health & PostgreSQL Migration Readiness
        │     └── Administrative Audit Trail Logger
        │
        └── IntelligenceView.tsx (Grounded AI Intelligence Console)
              ├── 3-Tier Explainable Output Display ([FACTS] / [RULES] / [SUMMARY])
              └── Anti-Hallucination Guardrail Refusal Banner
```

---

## 2. 3D Tactical Situation Map Architecture (`TacticalMap3D.tsx`)

1. **Scene Composition**:
   - `THREE.GridHelper(140, 35)` + Custom dark metallic terrain plane.
   - Ambient light (blue-gray) + Directional key light (electric cyan) + Red alert point lights.
   - Dynamic radar sweep arc rotating at $-1.5 \text{ rad/s}$.
2. **Entity Geometries**:
   - **Camera Masts**: Cylindrical masts with camera heads and extruded viewing frustum wireframe cones (illuminated in cyan when selected).
   - **Security Zones**: Extruded 3D wireframe volumes mapped from 2D polygon normalized coordinates.
   - **Target Markers**: Floating glowing spheres with ground beacon rings that pulse with real-time breach activity.
3. **Raycasting & Interaction**:
   - Mouse click raycaster detects camera masts and triggers instant camera focus and selection in the primary feed.
   - Orbit controls allow operators to drag-rotate (azimuth & elevation) and zoom into active threat sectors.
4. **Lifecycle & Memory Management**:
   - Automatic `renderer.dispose()` and event listener detachment on unmount to ensure 0 memory leaks during tab switching.

---

## 3. Real-Time Telemetry & WebSocket Event Bus Binding

```
[ WebSocket: /ws/events ]
             │
             ▼
   [ useWebSocket Hook ] (Auto-Reconnect with Exponential Backoff)
             │
             ▼
[ SurveillanceContext Store ] (Central React State)
             │
             ├─► alerts (Prepends latest breach event, plays audio chime if enabled)
             ├─► metrics (Updates AI processing FPS, inference latency, stride)
             ├─► threat (Recalculates DEFCON level, active breaches count)
             └─► cameras (Updates operational status, processed frame counts)
```

---

## 4. Performance & Frame Budgeting

- **60–90 FPS UI Render Target**: Component trees are optimized using `useMemo` and `useCallback` to prevent unnecessary re-renders.
- **Hardware Acceleration**: Three.js WebGL canvas runs on dedicated GPU threads with `powerPreference: 'high-performance'`.
- **Throttled Telemetry**: WebSocket event parsing is debounced to avoid layout thrashing during high-volume burst events.
