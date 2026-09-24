# Percepta - Autonomous Border Security & C2 Platform

## What This Is

An integrated AI-driven autonomous border surveillance, threat detection, and command-and-control (C2) web platform. It connects real-time video analytics, sensor fusion, radar/drone tracking, and interactive tactical mapping into a unified operational command center for national border defense.

## Core Value

Real-time zero-latency tactical situational awareness with automated intrusion detection and alert dispatching to defend borders.

## Requirements

### Validated

- [x] High-fidelity 3D Globe landing experience with realistic space environment and cinematic orbital telemetry.
- [x] Responsive cinematic scroll story with tuned dampening and multi-device support (mobile, tablet, desktop, TV).
- [x] Interactive C2 tactical loader with sound dispatch on initialize.
- [x] Tactical Authentication portal with email/password and multi-provider OAuth credentials.
- [x] High-performance Command Center UI with threat telemetry, camera streams, radar sector scans, and zero-globe tactical HUD layout.

### Active

- [ ] Real-time video inference feed integration (YOLO / OpenCV alert pipelines).
- [ ] WebSocket streaming telemetry between backend and frontend tactical stations.
- [ ] Multi-tier RBAC authorization for field operators, commanders, and system administrators.

### Out of Scope

- Earth globe inside the Command Center — Command Center must remain a focused tactical HUD without 3D globe rendering.
- Ambient audio on Landing Page — Audio strictly contained to tactical C2 loader sequence.

## Context

- Frontend: React 18, TypeScript, Vite, Vanilla CSS, Lucide icons, Three.js / Canvas space & orbit elements.
- Backend: FastAPI, Python, SQLite / PostgreSQL (Alembic migrations), Ultralytics YOLOv8 inference models.
- Environment: Windows, Antigravity IDE agentic pairing.

## Constraints

- **Performance**: Frame rate must maintain 60 FPS on tactical feeds without UI stutters.
- **Security**: Strict zero-trust authentication and authenticated WebSockets for telemetry.

## Key Decisions

| Decision | Context | Consequence |
|---|---|---|
| Remove 3D Earth from Command Center | Keep C2 screen clear, tactical, and distraction-free | Elevated tactical HUD with camera matrices, alerts, and map feeds |
| Loader audio single-shot | User experience during initial launch | Plays David Dumais Sci-Fi alert sound on mount without requiring tap |
| Multi-device CSS layers | TV, 4K, Desktop, Tablet, Mobile responsive breakpointing | Clean layout scaling across all viewports |
