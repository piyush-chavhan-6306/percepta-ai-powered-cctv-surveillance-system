import React from "react";
import type { ThreatLevel } from "../types/surveillance";
import { ShieldAlert, ShieldCheck, AlertCircle, AlertTriangle } from "lucide-react";

interface ThreatBadgeProps {
  level?: ThreatLevel;
  score?: number;
  showScore?: boolean;
}

export const ThreatBadge: React.FC<ThreatBadgeProps> = ({
  level = "DEFCON_GREEN",
  score,
  showScore = true,
}) => {
  const getBadgeConfig = () => {
    switch (level) {
      case "DEFCON_RED":
        return {
          label: "DEFCON 1 (CRITICAL)",
          className: "badge-red",
          icon: <ShieldAlert size={14} />,
        };
      case "DEFCON_ORANGE":
        return {
          label: "DEFCON 2 (HIGH)",
          className: "badge-orange",
          icon: <AlertTriangle size={14} />,
        };
      case "DEFCON_YELLOW":
        return {
          label: "DEFCON 3 (ELEVATED)",
          className: "badge-yellow",
          icon: <AlertCircle size={14} />,
        };
      case "DEFCON_GREEN":
      default:
        return {
          label: "DEFCON 4 (NOMINAL)",
          className: "badge-green",
          icon: <ShieldCheck size={14} />,
        };
    }
  };

  const config = getBadgeConfig();

  return (
    <span className={`badge ${config.className}`} style={{ fontSize: "0.78rem", padding: "0.3rem 0.65rem" }}>
      {config.icon}
      <span>{config.label}</span>
      {showScore && typeof score === "number" && (
        <span style={{ marginLeft: "0.25rem", opacity: 0.85 }}>[{score}/100]</span>
      )}
    </span>
  );
};
