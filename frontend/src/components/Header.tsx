import React, { useState } from "react";
import { useNavigate } from "react-router";
import {
  ChevronLeft,
  Plus,
  RefreshCw,
  Volume2,
  VolumeX,
  ShieldCheck,
  ShieldAlert,
  AlertTriangle,
} from "lucide-react";
import { PerceptaLogo } from "./PerceptaLogo";
import { useSurveillance } from "../store/surveillanceContext";
import { EdgeModeBadge } from "./EdgeModeIndicator";

interface HeaderProps {
  onRegisterFeed?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onRegisterFeed }) => {
  const navigate = useNavigate();
  const { threat, audioEnabled, setAudioEnabled, refreshAll, isLoading } = useSurveillance();
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Dynamic threat calculations from surveillance store
  const threatScore = Math.max(0, Math.min(100, Math.round(threat?.threat_score ?? 0)));
  const rawLevel = String(threat?.threat_level || "NORMAL").toUpperCase();
  let threatLevel = "NORMAL";
  if (rawLevel.includes("RED") || rawLevel.includes("CRITICAL") || threatScore >= 60) {
    threatLevel = "CRITICAL";
  } else if (rawLevel.includes("ORANGE") || rawLevel.includes("RESTRICTED") || threatScore >= 25) {
    threatLevel = "RESTRICTED";
  } else if (rawLevel.includes("YELLOW") || rawLevel.includes("ELEVATED") || threatScore >= 15) {
    threatLevel = "ELEVATED";
  } else {
    threatLevel = "NORMAL";
  }

  const getThreatConfig = (level: string) => {
    switch (level) {
      case "CRITICAL":
        return {
          ringColor: "#ff4757",
          badgeBg: "bg-[#ff4757]/15",
          badgeBorder: "border-[#ff4757]/40",
          badgeText: "text-[#ff4757]",
          Icon: ShieldAlert,
        };
      case "RESTRICTED":
        return {
          ringColor: "#f59e0b",
          badgeBg: "bg-[#f59e0b]/15",
          badgeBorder: "border-[#f59e0b]/40",
          badgeText: "text-[#f59e0b]",
          Icon: ShieldAlert,
        };
      case "ELEVATED":
        return {
          ringColor: "#eab308",
          badgeBg: "bg-[#eab308]/15",
          badgeBorder: "border-[#eab308]/40",
          badgeText: "text-[#eab308]",
          Icon: AlertTriangle,
        };
      default:
        return {
          ringColor: "#33f0b4",
          badgeBg: "bg-[#33f0b4]/15",
          badgeBorder: "border-[#33f0b4]/30",
          badgeText: "text-[#33f0b4]",
          Icon: ShieldCheck,
        };
    }
  };

  const threatConfig = getThreatConfig(threatLevel);
  const radius = 21;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference - (threatScore / 100) * circumference;

  const handleRefreshClick = async () => {
    setIsRefreshing(true);
    try {
      await refreshAll();
    } finally {
      setTimeout(() => setIsRefreshing(false), 500);
    }
  };

  return (
    <header className="h-[62px] border-b border-[#1b2530] bg-[#07090c]/95 backdrop-blur-md px-6 flex items-center justify-between z-30 shrink-0 font-sans select-none whitespace-nowrap overflow-hidden">
      {/* ── Left: Navigation & Branding (Proper Scale & Breathing Room) ── */}
      <div className="flex items-center gap-4 shrink-0">
        {/* < PORTAL Navigation Button */}
        <button
          type="button"
          onClick={() => navigate("/")}
          className="flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-mono font-semibold text-[#869099] hover:text-[#33f0b4] hover:bg-[#33f0b4]/10 transition-colors border border-[#1b2530] hover:border-[#33f0b4]/30 cursor-pointer shadow-sm"
        >
          <ChevronLeft size={14} />
          <span>PORTAL</span>
        </button>

        <div className="h-6 w-px bg-[#1b2530]" />

        {/* Brand Emblem & Title */}
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center shrink-0">
            <PerceptaLogo size={32} showText={false} />
          </div>

          <div className="flex flex-col justify-center leading-none">
            <div className="flex items-center gap-2.5">
              <h1 className="text-[15px] font-bold tracking-wider font-['Chakra_Petch',sans-serif] text-white uppercase">
                PERCEPTA DEFENSE C2
              </h1>
              <span className="text-[10px] px-2 py-0.5 font-mono font-bold tracking-wider rounded text-[#d6c19b] bg-[#d6c19b]/15 border border-[#d6c19b]/40 shadow-[0_0_8px_rgba(214,193,155,0.15)]">
                SIH26187
              </span>
            </div>
            <p className="text-[10px] font-mono text-[#8b9bb0] tracking-wider mt-1">
              Autonomous AI Border Surveillance Command
            </p>
          </div>
        </div>
      </div>

      {/* ── Center: Dynamic Circular Threat Assessment Gauge (Prominent Command Center Status) ── */}
      <div className="flex items-center gap-4 shrink-0 px-4 py-1.5 rounded-xl bg-[#090d13]/80 border border-[#1b2530]/60 shadow-[inset_0_1px_4px_rgba(0,0,0,0.5)]">
        <div className="relative w-[52px] h-[52px] flex items-center justify-center shrink-0">
          <svg viewBox="0 0 52 52" className="w-full h-full -rotate-90">
            {/* Background Track */}
            <circle
              cx="26"
              cy="26"
              r={radius}
              fill="none"
              stroke="rgba(255,255,255,0.07)"
              strokeWidth="3.6"
            />
            {/* Active Gauge Arc */}
            <circle
              cx="26"
              cy="26"
              r={radius}
              fill="none"
              stroke={threatConfig.ringColor}
              strokeWidth="3.6"
              strokeDasharray={circumference}
              strokeDashoffset={dashOffset}
              strokeLinecap="round"
              className="transition-all duration-700 ease-out"
              style={{
                filter: `drop-shadow(0 0 6px ${threatConfig.ringColor}60)`,
              }}
            />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center font-mono leading-none">
            <span className="text-[15px] font-black text-white tracking-tight">
              {threatScore}
            </span>
            <span className="text-[8.5px] text-[#8b9bb0] tracking-wider mt-0.5">
              / 100
            </span>
          </div>
        </div>

        <div className="flex flex-col justify-center gap-1">
          <div
            className={`flex items-center gap-1.5 px-3 py-1 rounded-full border text-[10.5px] font-mono font-bold tracking-wider uppercase shadow-sm ${threatConfig.badgeBg} ${threatConfig.badgeBorder} ${threatConfig.badgeText}`}
          >
            <threatConfig.Icon size={12} strokeWidth={2.2} />
            <span>{threatLevel}</span>
          </div>
          <span className="text-[8.5px] font-mono font-semibold text-[#8b9bb0] tracking-[0.16em] uppercase">
            THREAT ASSESSMENT
          </span>
        </div>
      </div>

      {/* ── Right: Edge Mode + Sensor/Audio Toggle + Add Camera + Refresh ── */}
      <div className="flex items-center gap-3 shrink-0">
        {/* Edge Mode Indicator */}
        <EdgeModeBadge />
        {/* Audio Toggle */}
        <button
          type="button"
          onClick={() => setAudioEnabled((prev) => !prev)}
          className={`h-9 w-9 rounded-md border transition-colors flex items-center justify-center cursor-pointer ${
            audioEnabled
              ? "text-[#33f0b4] bg-[#33f0b4]/10 border-[#33f0b4]/40 shadow-[0_0_8px_rgba(51,240,180,0.2)]"
              : "text-[#869099] border-[#1b2530] bg-[#0c1015] hover:text-[#cbd5e1] hover:bg-white/5"
          }`}
          title={audioEnabled ? "Alert Audio Active" : "Alert Audio Muted"}
        >
          {audioEnabled ? <Volume2 size={16} /> : <VolumeX size={16} />}
        </button>

        {/* + ADD CAMERA Prominent Tactical CTA Button */}
        <button
          type="button"
          onClick={onRegisterFeed}
          className="h-9.5 px-4.5 bg-[#33f0b4] hover:bg-[#28dfa3] active:scale-[0.98] text-black font-['Chakra_Petch',sans-serif] font-bold text-xs uppercase tracking-wider flex items-center gap-2 rounded-md shadow-[0_0_14px_rgba(51,240,180,0.35)] transition-all cursor-pointer"
        >
          <Plus size={15} strokeWidth={2.5} />
          <span>ADD CAMERA</span>
        </button>

        {/* Refresh Button */}
        <button
          type="button"
          onClick={handleRefreshClick}
          disabled={isLoading || isRefreshing}
          className="h-9 w-9 rounded-md border border-[#1b2530] text-[#869099] hover:text-white hover:border-[#263340] bg-[#0c1015] flex items-center justify-center transition-colors cursor-pointer shadow-sm"
          title="Refresh Telemetry & Stream State"
        >
          <RefreshCw
            size={14}
            className={isLoading || isRefreshing ? "animate-spin text-[#33f0b4]" : ""}
          />
        </button>
      </div>
    </header>
  );
};
