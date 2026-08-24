# BORDER INTELLIGENCE — COMPLETE DATA FLOW PIPELINES

**Project**: Border Intelligence (PS SIH26187)  
**Architecture**: Real-Time Asynchronous Multi-Stage Video Analytics Pipeline  

---

## Pipeline 1: Live CCTV Ingestion & Real-Time Event Dispatch

```
[ CCTV RTSP / Video Source ]
             │
             ▼ (OpenCV VideoCapture / Threaded Decoupling)
   [ Ingestion Adapter ]
             │
             ▼ (Bounded Ring Buffer - Max 60 Frames)
      [ FrameBuffer ]
             │
             ▼ (Adaptive Stride / Hardware Fallback)
    [ YOLOv8n Detector ]
             │
             ▼ (Bounding Boxes & Centroids)
   [ ByteTrack Tracker ]
             │
             ▼ (Persistent Track IDs & Trajectory)
    [ Kalman Prediction ]
             │
             ▼ (Ray-Casting Polygon Containment & Segment Intersect)
   [ Security Zone Monitor ]
             │
             ▼ (ZoneEvent & AlertEvent Schemas)
  ┌───────────────────────────────┐
  │   SQLite WAL EventStore       │ (Persist-Before-Publish Guarantee)
  └───────────────────────────────┘
                 │
                 ▼
       [ Async EventBus ]
                 │
                 ▼
   [ WebSocket /ws/events ] ───► [ React Command Center UI ]
```

---

## Pipeline 2: Camera Fleet Lifecycle & Reconnect Backoff

```
[ POST /api/cameras/register ]
             │
             ▼
    [ CameraManager ] ──► (Mask RTSP Password)
             │
             ▼ (Create Adapter & Thread Worker)
    [ Video / RTSP Adapter ]
             │
             ├──► [ Status: ONLINE ] ──► [ Start MJPEG Streamer ]
             │
             └──► [ Connection Dropped ]
                        │
                        ▼ (Exponential Backoff: 1s, 2s, 4s, ... max 30s)
               [ Auto-Reconnect Worker ]
                        │
                        ├──► [ Reconnected ] ──► [ Status: ONLINE ]
                        └──► [ Max Retries Failed ] ──► [ Status: DEGRADED / ERROR ]
```

---

## Pipeline 3: Spatial Intrusion & Loitering Incident Aggregation

```
[ TrackedObject Centroid: (x, y) ]
                 │
                 ├────────────────────────────────────────┐
                 ▼ (Point-in-Polygon Ray Casting)         ▼ (Line Segment Intersection)
   [ Polygon Security Zone ]               [ Virtual Tripwire Boundary ]
                 │                                        │
                 ├──► Transition: ENTERED                 └──► Transition: CROSSED
                 │         │                                        │
                 │         ▼                                        ▼
                 │   [ Dwell Clock Started ]              [ Critical Alert Generated ]
                 │         │                                        │
                 │         ▼ (Dwell > Loitering Threshold)          │
                 │   [ Loitering Alert Generated ]                  │
                 │                                                  │
                 └────────────────────────┬─────────────────────────┘
                                          ▼
                               [ Incident Aggregator ]
                                          │
                                          ▼
                          [ SQLite WAL Immutable Commit ]
```

---

## Pipeline 4: Grounded Natural-Language Intelligence Query

```
[ Operator Query: "Show recent security alerts" ]
                         │
                         ▼
        [ ControlledQueryLayer Input Sanitizer ]
                         │
                         ├──► [ Anti-Hallucination Guardrails ]
                         │          │
                         │          └──► [ Refusal Response if Biometric/Weapon/Intent/SQL ]
                         │
                         ▼ (Parameterized SQLAlchemy ORM)
             [ SQLite WAL Query Engine ]
                         │
                         ▼
          ┌────────────────────────────────────────┐
          │     3-Tier Grounded Synthesizer        │
          ├────────────────────────────────────────┤
          │ 1. [OBSERVED FACTS] (Raw DB Logs)      │
          │ 2. [DETERMINISTIC RULE RESULTS]        │
          │ 3. [AI INTERPRETATION / SUMMARY]       │
          └────────────────────────────────────────┘
                         │
                         ▼
      [ JSON GroundedQueryResponse to Operator ]
```

---

## Pipeline 5: Forensic Incident Dossier & SHA-256 Verification

```
[ Incident ID: INC-20260823-0004 ]
                 │
                 ▼ (Query all events where incident_id = 'INC-20260823-0004')
      [ SQLite WAL EventStore ]
                 │
                 ▼
      [ IncidentDossierEngine ]
                 │
                 ├──► [ Calculate Net Displacement & Heading Direction ]
                 ├──► [ Aggregate Zone Infractions & Dwell Timers ]
                 ├──► [ Compute Cryptographic Root SHA-256 Hash ]
                 └──► [ Generate Markdown Tactical SitRep ]
                 │
                 ▼
      [ Incident Dossier JSON / SitRep Modal ]
```

---

## Pipeline 6: Optical CCTV Diagnostics & Lens Tampering Evaluation

```
[ Raw Video Frame: (H x W x C) ]
                 │
                 ▼
    [ OpticalDiagnosticsEngine ]
                 │
                 ├──► [ Laplacian Variance: Focus / Blur Score ]
                 ├──► [ Grayscale Mean: Overall Brightness (0-255) ]
                 ├──► [ High Luminance Pixel Ratio: Blinding Glare Ratio ]
                 └──► [ Low Luminance Pixel Ratio: Darkness / Blackout Ratio ]
                 │
                 ▼
    ┌───────────────────────────────────────────────┐
    │ Camera Diagnostics Assessment State:          │
    │ • OPTIMAL (Laplacian > 100, Glare < 15%)      │
    │ • OCCLUDED_OR_BLURRED (Laplacian < 100)       │
    │ • BLINDED_GLARE (Glare > 30%)                 │
    │ • LOW_LIGHT_DEGRADED (Darkness > 70%)         │
    └───────────────────────────────────────────────┘
```

---

## Pipeline 7: Defense Multi-Modal Sensor Telemetry Ingestion

```
[ External Sensor: Radar / Seismic / Thermal IR / RF ]
                         │
                         ▼
             [ POST /api/sensors/ingest ]
                         │
                         ▼
              [ MultiModalSensorManager ]
                         │
                         ▼ (Typed Sensor Payload Normalization)
               [ SQLite WAL EventStore ]
                         │
                         ▼ (Future Cross-Modal Sensor Fusion Boundary)
            [ Sector Threat Level Recalculation ]
```
