import React from "react";
import { useNavigate } from "react-router";
import { useSurveillance } from "../store/surveillanceContext";
import {
  Video,
  AlertTriangle,
  Layers,
  Brain,
  FileCheck,
  Radio,
  Activity,
} from "lucide-react";

export const Navigation: React.FC = () => {
  const navigate = useNavigate();
  const { activeView, setActiveView, alerts } = useSurveillance();
  const unacknowledgedCount = alerts.filter((a) => !a.is_acknowledged).length;

  const navItems = [
    {
      id: "dashboard",
      label: "OBSERVE (COMMAND POST)",
      icon: <Video className="w-3.5 h-3.5" />,
    },
    {
      id: "analytics",
      label: "TACTICAL ANALYTICS",
      icon: <Activity className="w-3.5 h-3.5" />,
    },
    {
      id: "incidents",
      label: "INCIDENTS & THREAT",
      icon: <AlertTriangle className="w-3.5 h-3.5" />,
      badge: unacknowledgedCount > 0 ? unacknowledgedCount : undefined,
    },
    {
      id: "zones",
      label: "SECURITY ZONES",
      icon: <Layers className="w-3.5 h-3.5" />,
    },
    {
      id: "forensics",
      label: "EVIDENCE & FORENSICS",
      icon: <FileCheck className="w-3.5 h-3.5" />,
    },
    {
      id: "intelligence",
      label: "DEFENSE AI INTEL",
      icon: <Brain className="w-3.5 h-3.5" />,
    },
  ];

  return (
    <nav className="bg-[#050709]/95 border-b border-white/10 px-5 py-2 flex items-center justify-between flex-wrap gap-2 backdrop-blur-md">
      <div className="flex items-center gap-1.5 flex-wrap">
        {navItems.map((item) => {
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs font-['Barlow_Condensed',sans-serif] font-bold tracking-wider transition-all uppercase cursor-pointer ${
                isActive
                  ? "bg-[#9ee7df]/15 text-[#9ee7df] border border-[#9ee7df]/40 shadow-[0_0_14px_rgba(158,231,223,0.18)]"
                  : "text-[#849092] hover:text-white hover:bg-white/5 border border-transparent"
              }`}
            >
              {item.icon}
              <span>{item.label}</span>
              {item.badge !== undefined && (
                <span className="px-1.5 py-0.5 text-[8.5px] font-mono font-bold rounded-full bg-[#ff1744]/20 text-[#ff5252] border border-[#ff1744]/40">
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-3">
        <div className="text-[10px] font-mono text-[#556964] hidden md:flex items-center gap-1.5">
          <Radio className="w-2.5 h-2.5 text-[#00e676]" />
          <span>SECURE OPERATING PICTURE</span>
        </div>
      </div>
    </nav>
  );
};
