import { BorderWatchHero } from "../components/ui/border-watch-hero";
import { useSurveillance } from "../store/surveillanceContext";
import { ShieldAlert, Camera, Radar, MapPin, ArrowRight, Play } from "lucide-react";

export function LandingView() {
  const { setActiveView } = useSurveillance();

  const features = [
    {
      icon: Camera,
      label: "Existing CCTV Ingestion",
      desc: "Turn existing border cameras and RTSP/MP4 streams into intelligent surveillance nodes with 0 hardware replacement.",
      color: "#00e5ff",
    },
    {
      icon: Radar,
      label: "Persistent Object Tracking",
      desc: "ByteTrack + Kalman filters maintain continuous track IDs across sector boundaries even during temporary occlusion.",
      color: "#00e676",
    },
    {
      icon: MapPin,
      label: "Interactive Security Zones",
      desc: "Draw custom polygon perimeters and virtual tripwires directly onto camera feeds with automated breach alerts.",
      color: "#ffab00",
    },
    {
      icon: ShieldAlert,
      label: "Explainable Incident Evidence",
      desc: "Click any alert to inspect synchronized video playback, bounding boxes, and SHA-256 tamper-evident digital fingerprints.",
      color: "#ff1744",
    },
  ];

  return (
    <div style={{ background: "#05070a", minHeight: "calc(100vh - 100px)", paddingBottom: "2rem" }}>
      {/* Scroll-animated hero */}
      <BorderWatchHero
        frameCount={180}
        frameUrl={(i: number) => `/frames/border-cam/${String(i + 1).padStart(4, "0")}.webp`}
        titleTop="Border Intelligence"
        titleBottom="Command Post"
        accentHex="#08101a"
        onLaunchConsole={() => setActiveView("dashboard")}
      />

      {/* Action Strip & Capabilities Grid */}
      <section style={{ maxWidth: "1280px", margin: "0 auto", padding: "1.5rem 1.5rem 2.5rem" }}>
        {/* Quick Launch Action Bar */}
        <div
          style={{
            background: "linear-gradient(90deg, rgba(0, 229, 255, 0.08) 0%, rgba(14, 20, 31, 0.9) 100%)",
            border: "1px solid rgba(0, 229, 255, 0.25)",
            borderRadius: "6px",
            padding: "1rem 1.5rem",
            marginBottom: "2rem",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "1rem",
          }}
        >
          <div>
            <div style={{ fontSize: "0.95rem", fontWeight: 700, color: "#fff", fontFamily: "var(--font-display)", letterSpacing: "0.04em" }}>
              HACKATHON EVALUATION READY — PS SIH26187
            </div>
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", fontFamily: "var(--font-mono)", marginTop: "0.2rem" }}>
              Complete End-to-End Pipeline: Ingestion → Detection → Zone Rule → Incident → Grounded AI
            </div>
          </div>

          <div style={{ display: "flex", gap: "0.75rem" }}>
            <button
              onClick={() => setActiveView("simulation")}
              className="btn btn-primary"
              style={{ fontSize: "0.85rem", padding: "0.5rem 1rem", display: "flex", alignItems: "center", gap: "0.4rem" }}
            >
              <Play size={14} /> Run Live Demo <ArrowRight size={14} />
            </button>
            <button
              onClick={() => setActiveView("surveillance")}
              className="btn btn-secondary"
              style={{ fontSize: "0.85rem", padding: "0.5rem 1rem" }}
            >
              Surveillance Feeds Wall
            </button>
          </div>
        </div>

        {/* Feature Cards Grid */}
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(260px, 1fr))",
            gap: "1.25rem",
          }}
        >
          {features.map(({ icon: Icon, label, desc, color }) => (
            <div
              key={label}
              className="panel"
              style={{
                background: "rgba(14, 20, 31, 0.75)",
                border: "1px solid rgba(255, 255, 255, 0.08)",
                borderRadius: "6px",
                padding: "1.25rem",
                display: "flex",
                flexDirection: "column",
                gap: "0.75rem",
                transition: "border-color 0.2s ease, transform 0.2s ease",
              }}
            >
              <div
                style={{
                  width: 38,
                  height: 38,
                  borderRadius: 6,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  background: `${color}18`,
                  border: `1px solid ${color}40`,
                }}
              >
                <Icon size={19} color={color} />
              </div>
              <div>
                <div
                  style={{
                    fontFamily: "var(--font-display, sans-serif)",
                    fontWeight: 700,
                    fontSize: "0.92rem",
                    letterSpacing: "0.03em",
                    color: "#f1f5f9",
                    marginBottom: "0.35rem",
                  }}
                >
                  {label}
                </div>
                <div
                  style={{
                    fontFamily: "var(--font-mono, monospace)",
                    fontSize: "0.78rem",
                    color: "rgba(255, 255, 255, 0.55)",
                    lineHeight: 1.55,
                  }}
                >
                  {desc}
                </div>
              </div>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
