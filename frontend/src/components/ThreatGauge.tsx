import { useMemo } from "react";
import { motion } from "framer-motion";
import { ShieldAlert, ShieldCheck, AlertTriangle } from "lucide-react";

interface ThreatGaugeProps {
  score: number;
  level: string;
}function getLevelConfig(level: string, score: number = 0) {
  const normLevel = (level || "NORMAL").toUpperCase();
  if (normLevel === "CRITICAL" || normLevel === "DEFCON_RED" || normLevel === "RED" || score >= 60) {
    return {
      ring: "#ff1744",
      ring2: "#d50000",
      bg: "rgba(255,23,68,0.1)",
      border: "rgba(255,23,68,0.3)",
      text: "text-[#ff5252]",
      glow: "rgba(255,23,68,0.5)",
      pulse: "rgba(255,23,68,0.08)",
    };
  }
  if (
    normLevel === "RESTRICTED" ||
    normLevel === "HIGH" ||
    normLevel === "DEFCON_ORANGE" ||
    normLevel === "ORANGE" || score >= 25
  ) {
    return {
      ring: "#ff6d00",
      ring2: "#e65100",
      bg: "rgba(255,109,0,0.1)",
      border: "rgba(255,109,0,0.3)",
      text: "text-[#ff9100]",
      glow: "rgba(255,109,0,0.5)",
      pulse: "rgba(255,109,0,0.08)",
    };
  }
  if (
    normLevel === "ELEVATED" ||
    normLevel === "MODERATE" ||
    normLevel === "MEDIUM" ||
    normLevel === "DEFCON_YELLOW" ||
    normLevel === "YELLOW" || score >= 15
  ) {
    return {
      ring: "#ffab00",
      ring2: "#ff8f00",
      bg: "rgba(255,171,0,0.1)",
      border: "rgba(255,171,0,0.3)",
      text: "text-[#ffc400]",
      glow: "rgba(255,171,0,0.5)",
      pulse: "rgba(255,171,0,0.06)",
    };
  }
  return {
    ring: "#00e676",
    ring2: "#00c853",
    bg: "rgba(0,230,118,0.08)",
    border: "rgba(0,230,118,0.25)",
    text: "text-[#00e676]",
    glow: "rgba(0,230,118,0.45)",
    pulse: "rgba(0,230,118,0.06)",
  };
}

export function ThreatGauge({ score, level }: ThreatGaugeProps) {
  const config = useMemo(() => getLevelConfig(level, score), [level, score]);
  const clampedScore = Math.max(0, Math.min(100, Math.round(score)));

  const radius = 38;
  const radius2 = 42;
  const strokeWidth = 4;
  const strokeWidth2 = 1.5;
  const circumference = 2 * Math.PI * radius;
  const circumference2 = 2 * Math.PI * radius2;
  const arcLength = (270 / 360) * circumference;
  const arcLength2 = (270 / 360) * circumference2;
  const dashOffset = arcLength - (clampedScore / 100) * arcLength;
  const dashOffset2 = arcLength2 - (clampedScore / 100) * arcLength2;

  const Icon = score >= 75 ? ShieldAlert : score >= 50 ? AlertTriangle : ShieldCheck;

  return (
    <div className="flex items-center gap-4">
      {/* Gauge — double ring */}
      <div className="relative w-[96px] h-[96px]">
        {/* Ambient glow behind */}
        <motion.div
          className="absolute inset-[-12px] rounded-full blur-2xl"
          style={{ background: config.pulse }}
          animate={{ opacity: [0.4, 0.7, 0.4] }}
          transition={{ duration: 3, repeat: Infinity, ease: "easeInOut" }}
        />

        <svg viewBox="0 0 96 96" className="w-full h-full -rotate-[135deg] relative z-10">
          {/* Outer decorative ring */}
          <circle
            cx="48"
            cy="48"
            r={radius2}
            fill="none"
            stroke="rgba(255,255,255,0.04)"
            strokeWidth={strokeWidth2}
            strokeDasharray={`${arcLength2} ${circumference2}`}
            strokeLinecap="round"
          />
          <motion.circle
            cx="48"
            cy="48"
            r={radius2}
            fill="none"
            stroke={config.ring2}
            strokeWidth={strokeWidth2}
            strokeDasharray={`${arcLength2} ${circumference2}`}
            strokeLinecap="round"
            initial={{ strokeDashoffset: arcLength2 }}
            animate={{ strokeDashoffset: dashOffset2 }}
            transition={{ duration: 1.4, ease: [0.16, 1, 0.3, 1] }}
            style={{ opacity: 0.3 }}
          />

          {/* Inner track */}
          <circle
            cx="48"
            cy="48"
            r={radius}
            fill="none"
            stroke="rgba(255,255,255,0.06)"
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeLinecap="round"
          />

          {/* Active arc */}
          <motion.circle
            cx="48"
            cy="48"
            r={radius}
            fill="none"
            stroke={config.ring}
            strokeWidth={strokeWidth}
            strokeDasharray={`${arcLength} ${circumference}`}
            strokeLinecap="round"
            initial={{ strokeDashoffset: arcLength }}
            animate={{ strokeDashoffset: dashOffset }}
            transition={{ duration: 1.2, ease: [0.16, 1, 0.3, 1] }}
            style={{
              filter: `drop-shadow(0 0 10px ${config.glow}) drop-shadow(0 0 4px ${config.glow})`,
            }}
          />

          {/* Tick marks */}
          {Array.from({ length: 27 }).map((_, i) => {
            const angle = (i / 27) * 270;
            const rad = (angle * Math.PI) / 180;
            const r1 = radius - 6;
            const r2 = radius - 3;
            const x1 = 48 + r1 * Math.cos(rad);
            const y1 = 48 + r1 * Math.sin(rad);
            const x2 = 48 + r2 * Math.cos(rad);
            const y2 = 48 + r2 * Math.sin(rad);
            const isActive = i <= (clampedScore / 100) * 27;
            return (
              <line
                key={i}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={isActive ? config.ring : "rgba(255,255,255,0.1)"}
                strokeWidth={1}
                style={{ opacity: isActive ? 0.8 : 0.3 }}
              />
            );
          })}
        </svg>

        {/* Center content */}
        <div className="absolute inset-0 flex flex-col items-center justify-center z-20">
          <motion.span
            key={clampedScore}
            initial={{ scale: 0.7, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            transition={{ type: "spring", stiffness: 300, damping: 20 }}
            className="text-[22px] font-black font-mono text-foreground leading-none tracking-tight"
          >
            {clampedScore}
          </motion.span>
          <span className="text-[8px] font-mono text-muted-foreground mt-1 tracking-widest">
            / 100
          </span>
        </div>
      </div>

      {/* Level indicator */}
      <div className="flex flex-col gap-1.5">
        <motion.div
          key={level}
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4 }}
          className="flex items-center gap-2 px-3 py-1.5 rounded-xl border backdrop-blur-md"
          style={{
            background: config.bg,
            borderColor: config.border,
            boxShadow: `0 0 20px ${config.pulse}, inset 0 1px 0 rgba(255,255,255,0.05)`,
          }}
        >
          <Icon className={`w-4 h-4 ${config.text}`} />
          <span className={`text-[11px] font-mono font-bold uppercase tracking-widest ${config.text}`}>
            {level}
          </span>
        </motion.div>
        <span className="text-[9px] font-mono text-muted-foreground/60 px-1 tracking-wider">
          THREAT ASSESSMENT
        </span>
      </div>
    </div>
  );
}
