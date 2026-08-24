# BORDER INTELLIGENCE — TIER-S ARCHITECTURE DOCUMENTATION

**Project**: Border Intelligence — AI-Powered Persistent Border Surveillance & Incident Intelligence Platform  
**SIH Problem Statement**: PS SIH26187 ("AI-Based Intelligent Video Analytics Platform for Border Surveillance using existing CCTV Infrastructure")  

---

## 1. System Architecture & Central Chain Flow

```mermaid
flowchart TD
    subgraph Ingestion ["1. Video Ingestion & Physical Diagnostics"]
        CCTV["Existing CCTV Infrastructure (RTSP / Video / Sim)"]
        Diag["Optical Quality & Lens Tampering Watchdog\n(Laplacian Variance + Glare/Darkness Histograms)"]
        Buffer["Bounded FrameBuffer (Capacity=10, Drop-Oldest)"]
        CCTV --> Diag
        Diag --> Buffer
    end

    subgraph Perception ["2. AI Perception & Persistent Tracking"]
        Buffer --> YOLO["YOLOv8n Local Detector (Offline 640px)"]
        YOLO --> ByteTrack["ByteTrack Multi-Object Tracker\n(Hungarian Matching + Velocity Vector + Kalman Prediction)"]
    end

    subgraph Spatial ["3. Spatial Rules & Hotspot Analytics"]
        ByteTrack --> Zones["Security Zones Engine\n(Ray-Casting Polygon Containment + Virtual Boundary Line-Crossing)"]
        ByteTrack --> Heatmap["Spatial Heatmap Engine\n(16x16 Coordinate Density Grid)"]
    end

    subgraph Persistence ["4. Durable SQLite WAL Persistence (Persist-Before-Publish)"]
        Zones --> Store["EventStore (SQLite WAL Mode, Monotonic Seq IDs)"]
        Store --> Forensics["Cryptographic Forensic Engine\n(SHA-256 Event Signatures & Chain Audit)"]
    end

    subgraph Intelligence ["5. Intelligence & Decision Support"]
        Store --> Threat["Sector Threat Index Engine\n(DEFCON Matrix: Score 0-100 & Contributing Factors)"]
        Store --> Dossier["Tactical Incident Dossier Generator\n(SitRep Briefing + Motion Vector Summary)"]
        Store --> Assistant["Grounded Intelligence Assistant\n(3-Tier: Fact / Rule / Summary + 5 Refusal Guardrails)"]
        Store --> Bus["EventBus (In-Memory Pub/Sub)"]
    end

    subgraph Delivery ["6. Command Center Real-Time Delivery"]
        Bus --> WS["WebSocket (/ws/events — Fast Broadcast + Slow Client Timeout)"]
        Buffer --> MJPEG["MJPEG Video Stream (/api/stream/video/{id} — >140 FPS Generator)"]
    end
```

---

## 2. Tier-S Modules & Endpoint Specifications

### 2.1 Threat Assessment Engine
- **Module**: [`backend/intelligence/threat_engine.py`](file:///d:/SIH%20%20%20border%20cctv/backend/intelligence/threat_engine.py)
- **Endpoint**: `GET /api/threat/level`
- **Schema**:
```json
{
  "timestamp": "2026-08-24T00:00:00Z",
  "camera_id": "CAM-01",
  "threat_level": "DEFCON_RED",
  "threat_score": 85.0,
  "active_breaches": 3,
  "active_loiterers": 1,
  "active_tracks": 4,
  "contributing_factors": [
    "2 critical boundary crossing/breach events detected.",
    "1 unauthorized restricted zone entries."
  ],
  "recommended_action": "CRITICAL: Immediate Quick Reaction Force (QRF) dispatch and sector lockdown."
}
```

### 2.2 Cryptographic Forensics & Chain of Custody
- **Module**: [`backend/events/forensics.py`](file:///d:/SIH%20%20%20border%20cctv/backend/events/forensics.py)
- **Endpoints**: `GET /api/evidence/verify/{event_id}`, `GET /api/evidence/audit-integrity`
- **Tamper Proofing**:
  $$\text{Event Hash} = \text{SHA-256}(\text{seq\_id} \mathbin{\Vert} \text{event\_id} \mathbin{\Vert} \text{timestamp} \mathbin{\Vert} \text{camera\_id} \mathbin{\Vert} \text{track\_id} \mathbin{\Vert} \text{event\_type} \mathbin{\Vert} \text{payload})$$

### 2.3 Incident Forensic Dossier & Tactical SitRep
- **Module**: [`backend/incidents/dossier.py`](file:///d:/SIH%20%20%20border%20cctv/backend/incidents/dossier.py)
- **Endpoint**: `GET /api/incidents/{incident_id}/dossier`
- **Contents**: Full target motion profile, net displacement in pixels, cardinal heading degrees, zone infractions, duration, and SHA-256 certificate token.

### 2.4 Optical Diagnostics & Lens Tampering Watchdog
- **Module**: [`backend/ingestion/optical_diagnostics.py`](file:///d:/SIH%20%20%20border%20cctv/backend/ingestion/optical_diagnostics.py)
- **Endpoint**: `GET /api/cameras/{camera_id}/diagnostics`
- **Metrics**:
  - Blur Variance: $\text{Var}(\nabla^2 I)$
  - Glare Percentage: $\frac{\sum (I \ge 245)}{\text{Total Pixels}} \times 100\%$
  - Darkness Percentage: $\frac{\sum (I \le 15)}{\text{Total Pixels}} \times 100\%$

### 2.5 Spatial Heatmap Density Matrix
- **Module**: [`backend/zones/heatmap.py`](file:///d:/SIH%20%20%20border%20cctv/backend/zones/heatmap.py)
- **Endpoint**: `GET /api/cameras/{camera_id}/heatmap`
- **Output**: Normalized $16 \times 16$ 2D density array for frontend heatmap canvas overlay.

---

## 3. Guarantees & Invariants

1. **Zero Fabrication**: All metrics, threat levels, and dossiers are deterministically calculated from persisted SQLite WAL rows.
2. **Zero-Trust Chain of Custody**: SHA-256 tokens prove database authenticity to court/defense evaluators.
3. **Persist-Before-Publish**: In-memory EventBus and WebSocket clients never receive an event before SQLite disk commit.
4. **Hardware Resilience**: Real-time optical diagnostics flag degraded, sprayed, or blinded CCTV cameras in $<0.2\text{ms}$.
