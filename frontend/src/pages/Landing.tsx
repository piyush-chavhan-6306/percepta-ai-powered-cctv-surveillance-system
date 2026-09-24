import React, { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router";
import {
  ChevronRight,
  ArrowDown,
  Menu,
  X,
  ExternalLink,
} from "lucide-react";
import { EarthGlobe } from "../components/EarthGlobe";
import { PerceptaLogo } from "../components/PerceptaLogo";
import { TacticalCursor } from "../components/TacticalCursor";
import { C2Loader } from "../components/C2Loader";
import "../WorldOverlays.css";
import "../WorldMotion.css";

const stages = [
  {
    id: "observe",
    index: "01",
    title: "Observe",
    kicker: "THE WORLD IS ALWAYS IN MOTION",
    body: "A continuous field of cameras and sensors, made legible without asking operators to stare at noise.",
    metric: "LIVE / MULTI-CAMERA VISIBILITY",
    side: "left",
  },
  {
    id: "detect",
    index: "02",
    title: "Detect",
    kicker: "PERCEPTION WITH CONTEXT",
    body: "People, vehicles, faces, license plates, and zone intrusions — surfaced as signals, not spectacle.",
    metric: "PEOPLE  ·  VEHICLES  ·  PLATES",
    side: "right",
  },
  {
    id: "track",
    index: "03",
    title: "Track",
    kicker: "LOCAL SIGNAL → GLOBAL ENTITY",
    body: "A local track becomes a persistent entity across the places it appears. Continuity, with uncertainty made visible.",
    metric: "CAM-01  →  CAM-02  →  CAM-03",
    side: "left",
  },
  {
    id: "understand",
    index: "04",
    title: "Understand",
    kicker: "EVENTS ARE MORE THAN MOMENTS",
    body: "Zones, direction, dwell, persistence and camera context turn a detection into an event with meaning.",
    metric: "ZONE  /  MOVEMENT  /  DWELL",
    side: "right",
  },
  {
    id: "assess",
    index: "05",
    title: "Assess",
    kicker: "RISK IS NEVER JUST CONFIDENCE",
    body: "Threat assessment weighs observable factors. It separates what was seen from what it may mean.",
    metric: "72 / 100  ·  HIGH",
    side: "left",
  },
  {
    id: "evidence",
    index: "06",
    title: "Evidence",
    kicker: "EVERY SIGNAL NEEDS A SOURCE",
    body: "Target-specific frames, crops, timestamps and camera context keep intelligence grounded in what happened.",
    metric: "SOURCE FRAME  ·  TARGET CROP",
    side: "right",
  },
  {
    id: "incidents",
    index: "07",
    title: "Incidents",
    kicker: "MANY SIGNALS. ONE MEANINGFUL ALERT.",
    body: "Percepta reduces repeated detections into an incident an operator can understand and act on.",
    metric: "EVENTS  →  CONTEXT  →  INCIDENT",
    side: "left",
  },
  {
    id: "command",
    index: "08",
    title: "Command",
    kicker: "A CLEARER VIEW OF WHAT COMES NEXT",
    body: "From the first signal to the next action, the command layer gives teams a shared operating picture.",
    metric: "OPERATOR / EVIDENCE / ACTION",
    side: "left", // Positioned on left so command preview box sits completely free on right!
  },
];

interface OverlayTransform {
  opacity: number;
  scale: number;
  translateY: number;
}

interface WorldOverlaysProps {
  opacities: Record<string, OverlayTransform>;
}

function WorldOverlays({ opacities }: WorldOverlaysProps) {
  const getStyle = (id: string) => {
    const item = opacities[id] || { opacity: 0, scale: 0.94, translateY: 0 };
    return {
      opacity: item.opacity,
      transform: `scale(${item.scale}) translateY(${item.translateY}px)`,
      pointerEvents: item.opacity > 0.35 ? ("auto" as const) : ("none" as const),
      display: item.opacity > 0 ? "block" : "none",
    };
  };

  return (
    <div
      className="world-overlays"
      aria-live="polite"
      data-testid="world-story-overlays"
    >
      {/* ── 01. Observe ──────────────────────────────────────────────────────── */}
      <div
        className="overlay-stage-container"
        style={getStyle("observe")}
        data-testid="world-observe-overlay"
      >
        <div className="orbit-label orbit-cam cam-a">
          <span className="signal-dot" />
          CAM-01 <small>OPTICAL</small>
        </div>
        <div className="orbit-label orbit-cam cam-b active-anchor">
          <span className="signal-dot active-dot" />
          CAM-02 <small>IR · ACTIVE</small>
        </div>
        <div className="orbit-label orbit-cam cam-c">
          <span className="signal-dot" />
          CAM-03 <small>RGB</small>
        </div>
        {/* Subtle sensor network connection lines */}
        <svg className="camera-network-svg" aria-hidden="true">
          <line x1="58%" y1="28%" x2="74%" y2="44%" stroke="rgba(158,231,223,0.35)" strokeDasharray="3 3" />
          <line x1="74%" y1="44%" x2="64%" y2="70%" stroke="rgba(158,231,223,0.35)" strokeDasharray="3 3" />
        </svg>
        <span className="orbit-ring ring-one" />
        <span className="orbit-ring ring-two" />
      </div>

      {/* ── 02. Detect (Direct Anchor to CAM-02 Active Sensor) ─────────────────── */}
      <div
        className="overlay-stage-container"
        style={getStyle("detect")}
        data-testid="world-detect-overlay"
      >
        <div className="detection-field">
          {/* Active Locked Entity: PERSON-042 at CAM-02 */}
          <div className="tactical-box box-person tactical-box-corners ring-1 ring-[#9ee7df]/50 shadow-[0_0_24px_rgba(158,231,223,0.2)]">
            <div className="box-tag">
              <b className="text-[#9ee7df]">PERSON</b>
              <span className="box-conf">[0.94]</span>
            </div>
            <div className="box-reticle" />
            <div className="text-[7px] text-[#e8ebe6] font-mono font-medium mt-1">PERSON-042</div>
            <div className="text-[6.5px] text-[#9ee7df]/90 font-mono tracking-wider">LOCKED · CAM-02 [IR]</div>
          </div>

          {/* Vehicle Box */}
          <div className="tactical-box box-vehicle tactical-box-corners opacity-75">
            <div className="box-tag">
              <b>VEHICLE</b>
              <span className="box-conf">[0.89]</span>
            </div>
            <div className="box-reticle" />
            <div className="text-[6.5px] text-[#d6c19b]/80 font-mono">SUV · 24 KM/H</div>
          </div>

          {/* Plate Box */}
          <div className="tactical-box box-plate tactical-box-corners opacity-75">
            <div className="box-tag">
              <b>PLATE</b>
              <span className="box-conf">[0.92]</span>
            </div>
            <div className="text-[7px] text-[#e8ebe6] font-mono tracking-widest text-center mt-1">
              DL-04-AB-1982
            </div>
          </div>

          {/* Face Box */}
          <div className="tactical-box box-face tactical-box-corners opacity-75">
            <div className="box-tag">
              <b>FACE</b>
              <span className="box-conf">[0.95]</span>
            </div>
            <div className="box-reticle" />
            <div className="text-[6.5px] text-[#8fb8b5] font-mono">VERIFIED</div>
          </div>
        </div>
      </div>

      {/* ── 03. Track (Continuous Entity Handoff) ────────────────────────────── */}
      <div
        className="overlay-stage-container"
        style={getStyle("track")}
        data-testid="world-track-overlay"
      >
        <div className="track-journey-centered">
          <div className="track-id">
            <span className="flex items-center gap-1.5">
              <span className="w-1.5 h-1.5 rounded-full bg-[#9ee7df] shadow-[0_0_8px_#9ee7df]" />
              TRACK-017
            </span>
            <b>PERSON-042</b>
          </div>
          <div className="track-route">
            <span className="text-[#9ee7df] border-[#9ee7df]/40 font-medium">CAM-02 (ORIGIN)</span>
            <i />
            <span>CAM-01</span>
            <i />
            <span>CAM-03</span>
          </div>
          <small>CROSS-CAMERA CONTINUITY / SPATIAL-TEMPORAL HANDOFF</small>
        </div>
      </div>

      {/* ── 04. Understand (Entity Enters Zone Context) ──────────────────────── */}
      <div
        className="overlay-stage-container"
        style={getStyle("understand")}
        data-testid="world-understand-overlay"
      >
        <div className="context-radar-centered">
          <div className="radar-core">
            <span className="text-[7.5px] tracking-widest text-[#9ee7df] uppercase">
              RADAR CONTEXT · 14:32:18 UTC
            </span>
            <b>TRACK-017 [PERSON-042]</b>
          </div>
          <span className="context-tag zone">RESTRICTED ZONE</span>
          <span className="context-tag movement">PERIMETER INTRUSION</span>
          <span className="context-tag time">DWELL: 42s</span>
          <span className="context-tag direction">HEADING: 114° SE</span>
        </div>
      </div>

      {/* ── 05. Assess (Observable Risk Weighting) ───────────────────────────── */}
      <div
        className="overlay-stage-container"
        style={getStyle("assess")}
        data-testid="world-assess-overlay"
      >
        <div className="risk-reading-centered">
          <p>THREAT ASSESSMENT</p>
          <strong>
            72 <small>/ 100</small>
          </strong>
          <span>HIGH / CONTEXTUAL</span>
          <div>
            <i /> RESTRICTED-ZONE PERSISTENCE
          </div>
          <div>
            <i /> VECTOR: PERIMETER GATE 2
          </div>
          <div className="text-[7px] text-[#8fa09d] pt-2 font-mono">
            OBSERVABLE EVIDENCE WEIGHTING · NOT RAW CONFIDENCE
          </div>
        </div>
      </div>

      {/* ── 06. Evidence (Tamper-Evident Forensic Source) ────────────────────── */}
      <div
        className="overlay-stage-container"
        style={getStyle("evidence")}
        data-testid="world-evidence-overlay"
      >
        <div className="evidence-frame-centered">
          <div className="evidence-image">
            <span>FRAME 14:32:10 UTC</span>
          </div>
          <div>
            <p>EVIDENCE / TARGET CROP</p>
            <strong>PERSON-042</strong>
            <small>
              CAM-02 · SOURCE FRAME
              <br />
              REASON: RESTRICTED-ZONE ENTRY
              <br />
              SHA-256: 7f3a9e...c410 [VERIFIED]
            </small>
          </div>
        </div>
      </div>

      {/* ── 07. Incidents (Multi-Signal Convergence) ─────────────────────────── */}
      <div
        className="overlay-stage-container"
        style={getStyle("incidents")}
        data-testid="world-incidents-overlay"
      >
        <div className="incident-convergence-centered">
          <div className="incident-signals">
            <span>DWELL 42s</span>
            <span>ZONE BREACH</span>
            <span>TRACK ENTITY</span>
          </div>
          <div className="convergence-line">
            <i />
            <i />
            <i />
          </div>
          <div className="incident-result">
            <p>ONE MEANINGFUL INCIDENT</p>
            <strong>RESTRICTED-ZONE ENTRY</strong>
            <small>MULTIPLE SENSOR SIGNALS → CONVERGED INCIDENT</small>
          </div>
        </div>
      </div>

      {/* ── 08. Command (Clear Operating Picture) ───────────────────────────── */}
      <div
        className="overlay-stage-container"
        style={getStyle("command")}
        data-testid="world-command-overlay"
      >
        <div className="command-transition-right">
          <span className="text-[9px] tracking-widest text-[#9ee7df] uppercase font-bold">
            WORLD → OPERATING PICTURE
          </span>
          <div className="command-mini">
            <b>COMMAND CENTER</b>
            <em>
              <i /> CAM-01 · LIVE STREAMING
            </em>
            <span>OPERATING STATE: ACTIVE C2</span>
            <small>ACTIVE INCIDENTS · PERSISTENT TRACKS · EVIDENCE READY</small>
          </div>
        </div>
      </div>
    </div>
  );
}

interface PublicNavProps {
  onMenu: () => void;
  onNavigate: (sectionId: string) => void;
}

function PublicNav({ onMenu, onNavigate }: PublicNavProps) {
  const navigate = useNavigate();

  return (
    <header className="public-nav" data-testid="public-navigation">
      <Link to="/" className="flex items-center" data-testid="brand-home">
        <PerceptaLogo size={30} showText={true} />
      </Link>

      <nav className="nav-links">
        <button
          onClick={() => onNavigate("observe")}
          className="text-[10px] tracking-[0.15em] uppercase text-[#9da9aa] hover:text-[#9ee7df] transition-colors bg-transparent border-none cursor-pointer p-0"
          data-testid="nav-features"
        >
          FEATURES
        </button>
        <button
          onClick={() => onNavigate("track")}
          className="text-[10px] tracking-[0.15em] uppercase text-[#9da9aa] hover:text-[#9ee7df] transition-colors bg-transparent border-none cursor-pointer p-0"
          data-testid="nav-technology"
        >
          TECHNOLOGY
        </button>
        <button
          onClick={() => onNavigate("assess")}
          className="text-[10px] tracking-[0.15em] uppercase text-[#9da9aa] hover:text-[#9ee7df] transition-colors bg-transparent border-none cursor-pointer p-0"
          data-testid="nav-capabilities"
        >
          CAPABILITIES
        </button>
        <button
          onClick={() => onNavigate("command")}
          className="text-[10px] tracking-[0.15em] uppercase text-[#9da9aa] hover:text-[#9ee7df] transition-colors bg-transparent border-none cursor-pointer p-0"
          data-testid="nav-about"
        >
          ABOUT
        </button>
      </nav>

      <div className="nav-actions">
        <Link to="/auth" className="nav-login" data-testid="nav-login">
          AUTH
        </Link>
        <button
          onClick={() => navigate("/dashboard")}
          className="button button-small"
          data-testid="nav-demo"
        >
          ENTER C2 <ChevronRight size={14} />
        </button>
      </div>

      <button
        className="icon-button mobile-menu"
        onClick={onMenu}
        aria-label="Open menu"
        data-testid="mobile-menu-button"
      >
        <Menu size={20} />
      </button>
    </header>
  );
}

export default function Landing() {
  const navigate = useNavigate();
  const [progress, setProgress] = useState(0);
  const [menu, setMenu] = useState(false);
  const [stageOpacities, setStageOpacities] = useState<Record<string, OverlayTransform>>({
    observe: { opacity: 0, scale: 0.94, translateY: 0 },
    detect: { opacity: 0, scale: 0.94, translateY: 0 },
    track: { opacity: 0, scale: 0.94, translateY: 0 },
    understand: { opacity: 0, scale: 0.94, translateY: 0 },
    assess: { opacity: 0, scale: 0.94, translateY: 0 },
    evidence: { opacity: 0, scale: 0.94, translateY: 0 },
    incidents: { opacity: 0, scale: 0.94, translateY: 0 },
    command: { opacity: 0, scale: 0.94, translateY: 0 },
  });

  // Per-stage title opacity & transforms for the scroll exit (center -> top -> fade out / disappear)
  const [titleTransforms, setTitleTransforms] = useState<Record<string, { opacity: number; translateY: number }>>({});

  useEffect(() => {
    let ticking = false;

    const updatePositions = () => {
      const viewportCenter = window.innerHeight / 2;
      const maxDistance = window.innerHeight * 0.48;
      const nextOpacities: Record<string, OverlayTransform> = {};
      const nextTitles: Record<string, { opacity: number; translateY: number }> = {};

      // Navbar height threshold: navbar is ~72px tall
      const NAV_THRESHOLD = 82;

      // 0. Hero Title Exit (purely scroll-driven: 100% visible at scrollY=0, smoothly disappears as you scroll down)
      const heroScrollDist = window.innerHeight * 0.45;
      const heroProgress = Math.min(1, Math.max(0, window.scrollY / Math.max(1, heroScrollDist)));
      const heroOpacity = Math.max(0, 1 - Math.pow(heroProgress, 1.2));
      const heroTranslate = heroProgress * -45;
      nextTitles["hero"] = { opacity: heroOpacity, translateY: heroTranslate };

      // 1–8. Choreographed Stages
      stages.forEach((stage) => {
        const el = document.getElementById(stage.id);
        if (!el) {
          nextOpacities[stage.id] = { opacity: 0, scale: 0.94, translateY: 0 };
          nextTitles[stage.id] = { opacity: 1, translateY: 0 };
          return;
        }

        const copyEl = (el.querySelector(".stage-copy") as HTMLElement) || el;
        const copyRect = copyEl.getBoundingClientRect();
        const copyTop = copyRect.top;

        // WHEN TITLE REACHES NAVBAR: BOTH TITLE AND OVERLAY OBJECT DISAPPEAR!
        if (copyTop <= NAV_THRESHOLD) {
          nextOpacities[stage.id] = { opacity: 0, scale: 0.94, translateY: -15 };
          nextTitles[stage.id] = { opacity: 0, translateY: -45 };
          return;
        }

        // Center reading zone: comfortable plateau of full visibility around optical center
        const PLATEAU_HALF = 70;
        const plateauTop = viewportCenter - PLATEAU_HALF;
        const plateauBottom = viewportCenter + PLATEAU_HALF;

        if (copyTop < plateauTop) {
          // Moving from plateau UPWARD towards navbar:
          // Smoothly fade out both the title and the overlay object
          const progressToNav = Math.min(
            1,
            Math.max(0, (plateauTop - copyTop) / (plateauTop - NAV_THRESHOLD))
          );
          const exitFade = Math.max(0, 1 - Math.pow(progressToNav, 1.15));
          const titleTranslate = progressToNav * -45;
          const overlayTranslate = progressToNav * -15;

          nextTitles[stage.id] = {
            opacity: exitFade,
            translateY: titleTranslate,
          };
          nextOpacities[stage.id] = {
            opacity: exitFade,
            scale: 0.95 + 0.05 * exitFade,
            translateY: overlayTranslate,
          };
        } else if (copyTop <= plateauBottom) {
          // Inside prime reading plateau: 100% fully emerged and crisp!
          nextTitles[stage.id] = {
            opacity: 1,
            translateY: 0,
          };
          nextOpacities[stage.id] = {
            opacity: 1,
            scale: 1,
            translateY: 0,
          };
        } else {
          // Coming from below into plateau:
          const enterDistance = window.innerHeight * 0.45;
          const progressEnter = Math.min(
            1,
            Math.max(0, (copyTop - plateauBottom) / enterDistance)
          );
          const enterFade = Math.max(0, 1 - Math.pow(progressEnter, 1.2));
          const titleTranslate = progressEnter * 30;
          const overlayTranslate = progressEnter * 15;

          nextTitles[stage.id] = {
            opacity: enterFade,
            translateY: titleTranslate,
          };
          nextOpacities[stage.id] = {
            opacity: enterFade,
            scale: 0.95 + 0.05 * enterFade,
            translateY: overlayTranslate,
          };
        }
      });

      setStageOpacities(nextOpacities);
      setTitleTransforms(nextTitles);

      const maxScroll = document.body.scrollHeight - window.innerHeight;
      setProgress(maxScroll > 0 ? Math.min(1, Math.max(0, window.scrollY / maxScroll)) : 0);
      ticking = false;
    };

    const handleScroll = () => {
      if (!ticking) {
        requestAnimationFrame(updatePositions);
        ticking = true;
      }
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    updatePositions();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  // ── Smooth Programmatic Scroll To Section ─────────────────────────────────
  const scrollToSection = (id: string) => {
    if (id === "hero") {
      window.scrollTo({ top: 0, behavior: "smooth" });
      window.dispatchEvent(
        new CustomEvent("percepta-sync-scroll", { detail: { targetY: 0 } })
      );
      return;
    }

    const el = document.getElementById(id);
    if (el) {
      // Find the inner stage-copy element so we center the text block, not just the section top
      const copyEl = (el.querySelector(".stage-copy") as HTMLElement) || el;
      const copyRect = copyEl.getBoundingClientRect();
      // Target the comfortable optical reading center of the viewport (46% of window.innerHeight)
      const targetViewportY = window.innerHeight * 0.46;
      const topOffset = Math.max(0, Math.round(copyRect.top + window.scrollY - targetViewportY));

      window.scrollTo({
        top: topOffset,
        behavior: "smooth",
      });
      window.dispatchEvent(
        new CustomEvent("percepta-sync-scroll", { detail: { targetY: topOffset } })
      );
    }
  };

  // Support initial hash navigation if URL contains #track, #observe, etc.
  useEffect(() => {
    const hash = window.location.hash.replace("#", "");
    if (hash) {
      const timer = setTimeout(() => {
        scrollToSection(hash);
      }, 250);
      return () => clearTimeout(timer);
    }
  }, []);

  // ── Controlled Cinematic Smooth Scroll Damper ─────────────────────────────
  useEffect(() => {
    let targetY = window.scrollY;
    let currentY = window.scrollY;
    let isWheeling = false;
    let animId: number | null = null;

    const originalScrollBehavior = document.documentElement.style.scrollBehavior;
    document.documentElement.style.scrollBehavior = "auto";

    const smoothStep = () => {
      const diff = targetY - currentY;
      if (Math.abs(diff) < 0.35) {
        currentY = targetY;
        window.scrollTo(0, currentY);
        isWheeling = false;
        animId = null;
        return;
      }

      currentY += diff * 0.12; // Silky smooth, responsive, cinematic momentum drift
      window.scrollTo(0, currentY);
      animId = requestAnimationFrame(smoothStep);
    };

    const handleWheel = (e: WheelEvent) => {
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      e.preventDefault();

      const maxScroll = Math.max(
        0,
        document.documentElement.scrollHeight - window.innerHeight
      );

      targetY = Math.max(0, Math.min(maxScroll, targetY + e.deltaY * 0.35));

      if (!isWheeling) {
        isWheeling = true;
        currentY = window.scrollY;
        animId = requestAnimationFrame(smoothStep);
      }
    };

    const handleManualScroll = () => {
      if (!isWheeling) {
        targetY = window.scrollY;
        currentY = window.scrollY;
      }
    };

    const handleSync = (e: any) => {
      if (typeof e.detail?.targetY === "number") {
        targetY = e.detail.targetY;
        currentY = window.scrollY;
        isWheeling = false;
        if (animId) {
          cancelAnimationFrame(animId);
          animId = null;
        }
      }
    };

    window.addEventListener("wheel", handleWheel, { passive: false });
    window.addEventListener("scroll", handleManualScroll, { passive: true });
    window.addEventListener("percepta-sync-scroll", handleSync);

    return () => {
      document.documentElement.style.scrollBehavior = originalScrollBehavior;
      window.removeEventListener("wheel", handleWheel);
      window.removeEventListener("scroll", handleManualScroll);
      window.removeEventListener("percepta-sync-scroll", handleSync);
      if (animId) cancelAnimationFrame(animId);
    };
  }, []);

  return (
    <main className="landing selection:bg-[#9ee7df] selection:text-[#050709]" data-testid="landing-page">
      <TacticalCursor />
      <PublicNav onMenu={() => setMenu(!menu)} onNavigate={scrollToSection} />

      {/* Mobile Drawer Navigation */}
      {menu && (
        <div className="mobile-nav" data-testid="mobile-navigation">
          <button onClick={() => setMenu(false)} data-testid="mobile-close-button">
            <X size={20} />
          </button>
          <div className="mb-6">
            <PerceptaLogo size={26} showText={true} />
          </div>
          {["observe", "detect", "track", "understand", "assess", "evidence", "incidents", "command"].map(
            (x) => (
              <button
                key={x}
                onClick={() => {
                  setMenu(false);
                  scrollToSection(x);
                }}
                className="text-left font-mono tracking-wider py-2 uppercase hover:text-[#9ee7df] transition-colors bg-transparent border-none cursor-pointer"
                data-testid={`mobile-nav-${x}`}
              >
                {x.toUpperCase()}
              </button>
            )
          )}
          <button
            onClick={() => {
              setMenu(false);
              navigate("/dashboard");
            }}
            className="button mt-6 text-center w-full justify-center"
          >
            LAUNCH C2 CONSOLE →
          </button>
          <button
            onClick={() => {
              setMenu(false);
              navigate("/auth");
            }}
            className="button button-ghost mt-3 text-center w-full justify-center"
          >
            OPERATOR AUTH // LOGIN →
          </button>
        </div>
      )}

      {/* Telemetry Progress Bar */}
      <div className="landing-progress">
        <span style={{ transform: `scaleX(${progress})` }} />
      </div>

      {/* 3D Photorealistic Earth Scene + Centered Overlays */}
      <div className="earth-layer">
        <EarthGlobe progress={progress} />
        <WorldOverlays opacities={stageOpacities} />
        <div
          className="earth-caption"
          style={{
            opacity: progress > 0.04 ? 1 : 0,
            transition: "opacity 0.4s ease",
            pointerEvents: "none",
          }}
        >
          <span /> GLOBAL INTELLIGENCE / 00
          {Math.min(9, Math.floor(progress * 10) + 1)}
        </div>
      </div>

      {/* ── 00. Hero Section (Pristine, No Telemetry Noise) ─────────────────── */}
      <section className="hero-story" id="hero" data-testid="hero-section">
        <div
          className="hero-copy"
          style={{
            opacity: titleTransforms["hero"]?.opacity ?? 1,
            transform: `translateY(${titleTransforms["hero"]?.translateY ?? 0}px)`,
            pointerEvents: (titleTransforms["hero"]?.opacity ?? 1) > 0.2 ? "auto" : "none",
          }}
        >
          <p className="eyebrow">
            <span className="eyebrow-line" /> INTELLIGENCE, GROUNDED
          </p>
          <h1>
            See the
            <br />
            <em>whole</em> picture.
          </h1>
          <p className="hero-description">
            Percepta transforms distributed surveillance data into actionable intelligence — from the
            first signal to the next authorized decision.
          </p>

          {/* Hero Action Button Group */}
          <div className="flex flex-wrap items-center gap-4 mt-8 mb-6 pt-2">
            <button
              onClick={() => navigate("/dashboard")}
              className="button font-mono text-xs py-3 px-6 flex items-center gap-2 cursor-pointer shadow-[0_0_20px_rgba(158,231,223,0.25)] hover:shadow-[0_0_28px_rgba(158,231,223,0.4)] transition-all active:scale-[0.98]"
            >
              <span>ENTER COMMAND CONSOLE</span>
              <ChevronRight size={14} />
            </button>
            <button
              onClick={() => navigate("/auth")}
              className="button button-ghost font-mono text-xs py-3 px-5 flex items-center gap-2 cursor-pointer hover:border-[#9ee7df]/50 transition-all active:scale-[0.98]"
            >
              <span>OPERATOR AUTH // ACCESS</span>
            </button>
          </div>

          <button
            onClick={() => scrollToSection("observe")}
            className="scroll-prompt cursor-pointer bg-transparent border-none text-left p-0 mt-8 hover:text-white transition-colors"
            data-testid="hero-scroll-link"
          >
            <span className="scroll-icon">
              <ArrowDown size={15} />
            </span>
            SCROLL TO EXPLORE CHAPTERS
          </button>
        </div>
        <div
          className="hero-side-note"
          style={{
            opacity: titleTransforms["hero"]?.opacity ?? 1,
          }}
        >
          <span>01</span>
          <span className="vertical-rule" />
          <span>THE PERCEPTA SYSTEM</span>
        </div>
      </section>

      {/* ── 01–08. The 8 Choreographed Chapters ─────────────────────────────── */}
      <div className="story-track">
        {stages.map((stage) => {
          const tStyle = titleTransforms[stage.id] || { opacity: 1, translateY: 0 };
          return (
            <section
              key={stage.id}
              className={`story-stage stage-${stage.side}`}
              id={stage.id}
              data-testid={`story-stage-${stage.id}`}
            >
              <div
                className="stage-index"
                style={{
                  opacity: tStyle.opacity,
                  pointerEvents: tStyle.opacity > 0.2 ? "auto" : "none",
                }}
              >
                {stage.index}
                <span />
              </div>
              <div
                className="stage-copy"
                style={{
                  opacity: tStyle.opacity,
                  transform: `translateY(${tStyle.translateY}px)`,
                  pointerEvents: tStyle.opacity > 0.2 ? "auto" : "none",
                }}
              >
                <p className="eyebrow">{stage.kicker}</p>
                <h2>
                  {stage.title}
                  <sup>.</sup>
                </h2>
                <p className="stage-body">{stage.body}</p>
                <div className="telemetry-line">
                  <span>{stage.metric}</span>
                  <ChevronRight size={15} />
                </div>
              </div>
            </section>
          );
        })}
      </div>

      {/* ── 09. Grounded Defense AI Section (Clean Final CTA, Clutter-Free) ─── */}
      <section
        className="final-cta min-h-screen py-28 px-6 md:px-16 lg:px-24 flex flex-col justify-center relative z-10"
        id="final-cta"
        data-testid="final-cta"
      >
        <div className="w-full max-w-5xl text-left space-y-8">
          <p className="eyebrow flex items-center gap-3">
            <span className="eyebrow-line" /> GROUNDED DEFENSE AI
          </p>

          <h2 className="text-6xl sm:text-7xl lg:text-9xl font-['Barlow_Condensed'] uppercase tracking-tight text-[#e8ebe6] leading-[0.85]">
            Make sense
            <br />
            of what <em className="text-[#d6c19b] not-italic">matters</em>.
          </h2>

          <p className="text-base sm:text-lg text-[#a5b0ae] font-mono leading-relaxed max-w-xl">
            Percepta is the intelligence layer between sensing and acting. It synthesizes optical
            feeds, spatial tracking, and threat analytics into verifiable facts.
          </p>

          <div className="flex flex-wrap items-center gap-5 pt-4">
            <button
              onClick={() => navigate("/dashboard")}
              className="button font-mono text-xs py-4 px-6"
              data-testid="view-demo-button"
            >
              ENTER COMMAND CONSOLE <ChevronRight size={15} />
            </button>
            <button
              onClick={() => navigate("/incidents")}
              className="button button-ghost font-mono text-xs py-4 px-6"
              data-testid="book-demo-button"
            >
              INCIDENTS DOSSIER
            </button>
            <button
              onClick={() => navigate("/forensics")}
              className="text-link font-mono text-xs ml-2"
            >
              FORENSIC REPLAY <ExternalLink size={13} />
            </button>
          </div>
        </div>

        {/* Bottom Footer Signature */}
        <div className="footer-signature w-full max-w-5xl flex flex-col sm:flex-row justify-between items-center gap-4 text-[9px] font-mono text-[#667273] border-t border-[rgba(207,220,214,0.16)] pt-6 mt-20">
          <span>PERCEPTA DEFENSE OPERATING SYSTEM</span>
          <span>MULTI-MODAL CCTV & GEO-INTELLIGENCE COMMAND</span>
          <span>© 2026 CONFIDENTIAL DEFENSE SYSTEMS</span>
        </div>
      </section>
    </main>
  );
}
