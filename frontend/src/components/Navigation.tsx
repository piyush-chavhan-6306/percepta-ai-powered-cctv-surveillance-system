import React from "react";
import { useSurveillance } from "../store/surveillanceContext";
import {
  Video,
  AlertTriangle,
  Layers,
  Bot,
  FileCheck,
} from "lucide-react";

export const Navigation: React.FC = () => {
  const { activeView, setActiveView, alerts } = useSurveillance();

  const unacknowledgedCount = alerts.filter((a) => !a.is_acknowledged).length;

  const navItems = [
    {
      id: "dashboard",
      label: "LIVE MONITORING",
      icon: <Video className="w-4 h-4" />,
    },
    {
      id: "incidents",
      label: "ALERTS & INCIDENTS",
      icon: <AlertTriangle className="w-4 h-4" />,
      badge: unacknowledgedCount > 0 ? unacknowledgedCount : undefined,
      badgeColor: "bg-[#ff1744] text-white",
    },
    {
      id: "zones",
      label: "SECURITY ZONES",
      icon: <Layers className="w-4 h-4" />,
    },
    {
      id: "intelligence",
      label: "AI OPERATOR ASSISTANT",
      icon: <Bot className="w-4 h-4" />,
    },
    {
      id: "forensics",
      label: "EVIDENCE & FORENSICS",
      icon: <FileCheck className="w-4 h-4" />,
    },
  ];

  return (
    <nav className="bg-[#0a0f18] border-b border-white/10 px-5 py-2 flex items-center justify-between flex-wrap gap-2">
      <div className="flex items-center gap-1.5 flex-wrap">
        {navItems.map((item) => {
          const isActive = activeView === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveView(item.id)}
              className={`flex items-center gap-2 px-3 py-1.5 rounded text-xs font-display font-bold tracking-wider transition-all ${
                isActive
                  ? "bg-[#00e5ff]/15 text-[#00e5ff] border border-[#00e5ff]/40 shadow-[0_0_10px_rgba(0,229,255,0.15)]"
                  : "bg-transparent text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent"
              }`}
            >
              {item.icon}
              <span>{item.label}</span>
              {item.badge !== undefined && (
                <span className={`px-1.5 py-0.2 text-[10px] font-mono-tech font-bold rounded-full ${item.badgeColor}`}>
                  {item.badge}
                </span>
              )}
            </button>
          );
        })}
      </div>

      <div className="text-[11px] font-mono-tech text-gray-500 hidden sm:block">
        CORE SURVEILLANCE MVP • 0 FAKE DATA
      </div>
    </nav>
  );
};
