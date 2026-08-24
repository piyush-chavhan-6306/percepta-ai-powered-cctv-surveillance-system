# BORDER INTELLIGENCE — COMMAND CENTER UI DESIGN SYSTEM

**Design Philosophy**: Tactical Defense & Aerospace Intelligence Command Post (C2)  
**Target Visual Bar**: Mission-Critical Military Defense HUD, Layered Spatial Glassmorphism, 3D Situational Awareness  
**Target Resolutions**: 1920×1080 (Primary Full HD), 2560×1440 (2K QHD), 3840×2160 (4K UHD Command Wall)  

---

## 1. Color System (Semantic Defense Palette)

### Background & Surface Hierarchy
```css
--bg-darkest: #05070a;          /* Deep void canvas */
--bg-primary: #080c13;          /* Main workspace foundation */
--bg-surface: #0e141f;          /* Elevated tactical card background */
--bg-surface-raised: #141c2b;   /* Active module highlight */
--bg-glass: rgba(14, 20, 31, 0.82); /* 16px blurred translucent glass panel */
```

### Semantic Accent Colors
| Semantic Meaning | Color Variable | Hex Code | Purpose & Usage |
| :--- | :--- | :--- | :--- |
| **Telemetry / System Active** | `--c2-cyan` | `#00e5ff` | Live telemetry readouts, radar sweep, 3D camera cones, focus rings |
| **Secure / Nominal** | `--c2-emerald` | `#00e676` | DEFCON 4, online camera feeds, cryptographic authentic checks |
| **Warning / Elevated Dwell** | `--c2-amber` | `#ffab00` | DEFCON 3, loitering dwell timers approaching threshold |
| **High Threat / Imminent** | `--c2-orange` | `#ff6d00` | DEFCON 2, perimeter boundary proximity |
| **Critical Breach / Emergency** | `--c2-crimson` | `#ff1744` | DEFCON 1, restricted zone breach, tripwire crossing, QRF dispatch |
| **Analytical / Spatial** | `--c2-blue` | `#2979ff` | Heatmap density corridors, velocity vectors, persistent track IDs |

---

## 2. Technical Typography Hierarchy

| Hierarchy Level | Font Family | Weight | Size & Tracking | Typical Application |
| :--- | :--- | :--- | :--- | :--- |
| **Mission / Threat Title** | `Orbitron`, sans-serif | 800-900 | 24px - 32px (`0.06em`) | DEFCON Level, Threat Score, Mission HUD |
| **Sector & Card Titles** | `Rajdhani`, sans-serif | 700 | 14px - 18px (`0.04em`) | Camera Titles, Incident IDs, View Headers |
| **Telemetry & Metrics** | `JetBrains Mono`, monospace | 600-700 | 11px - 14px | AI FPS, latency ms, SHA-256 tokens, timestamps |
| **Body & Explanations** | `Inter`, sans-serif | 400-500 | 12px - 14px | Grounded facts, operator notes, incident summaries |

---

## 3. Spatial & Surface Components

### 1. HUD Card (`.hud-card`)
- Corner brackets on top-left and bottom-right in electric cyan.
- Dark graphite background with subtle 1px border.

### 2. Glass Panel (`.glass-panel`)
- Background: `rgba(14, 20, 31, 0.82)`.
- Backdrop filter: `blur(16px)`.
- Inset light reflection on top edge (`inset 0 1px 0 rgba(255, 255, 255, 0.08)`).

### 3. Tactical Grid (`.tactical-grid-bg`)
- 32px x 32px subtle grid overlay providing aerospace telemetry depth without distraction.

---

## 4. Micro-Interactions & Animation Guidelines

- **Restrained Motion**: Animations are strictly functional (radar sweep at 4s rotation, alert ping on unacknowledged breaches, smooth 700ms SVG radial threat gauge interpolation).
- **Zero Gimmicks**: No gratuitous bouncing, neon flaring, or spinning coins. Every visual transition conveys real-time system state changes.
