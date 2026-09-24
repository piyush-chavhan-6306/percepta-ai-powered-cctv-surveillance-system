import React from "react";
import { useSurveillance } from "../store/surveillanceContext";
import {
  Monitor,
  Camera,
  AlertTriangle,
  Users,
  FileText,
  Layers,
  Brain,
  Activity,
} from "lucide-react";

export const SidebarNav: React.FC = () => {
  const { activeView, setActiveView, alerts } = useSurveillance();
  const unacknowledgedCount = alerts.filter((a) => !a.is_acknowledged).length || 3;

  const navItems = [
    {
      id: "dashboard",
      label: "COMMAND CENTER",
      icon: Monitor,
    },
    {
      id: "analytics",
      label: "TACTICAL ANALYTICS",
      icon: Activity,
    },
    {
      id: "cameras",
      label: "CAMERAS",
      icon: Camera,
    },
    {
      id: "incidents",
      label: "INCIDENTS",
      icon: AlertTriangle,
      badge: unacknowledgedCount > 0 ? unacknowledgedCount : undefined,
    },
    {
      id: "entities",
      label: "GLOBAL ENTITIES",
      icon: Users,
    },
    {
      id: "forensics",
      label: "EVIDENCE",
      icon: FileText,
    },
    {
      id: "zones",
      label: "ZONES",
      icon: Layers,
    },
    {
      id: "intelligence",
      label: "GROUNDED DEFENSE AI",
      icon: Brain,
    },
    {
      id: "telemetry",
      label: "SYSTEM TELEMETRY",
      icon: Activity,
    },
  ];

  return (
    <aside className="w-64 shrink-0 bg-[#07090c] border-r border-[#171e27] flex flex-col justify-between py-5 select-none font-mono min-h-[calc(100vh-53px)]">
      {/* ── Navigation Links (Stitch Brutalist Precision) ── */}
      <div className="flex flex-col gap-1 px-3">
        {navItems.map((item) => {
          const isActive = activeView === item.id;
          const IconComponent = item.icon;

          return (
            <button
              key={item.id}
              type="button"
              onClick={() => setActiveView(item.id)}
              className={`w-full flex items-center justify-between px-3.5 py-2.5 rounded-none text-xs font-mono tracking-[0.16em] uppercase transition-all relative group cursor-pointer border ${
                isActive
                  ? "bg-[#38e8cb]/10 text-[#38e8cb] border-[#38e8cb]/40 shadow-[inset_0_0_12px_rgba(56,232,203,0.06)]"
                  : "text-[#8492a6] hover:text-white hover:bg-[#0c1017] border-transparent"
              }`}
            >
              <div className="flex items-center gap-3">
                {isActive ? (
                  <span className="w-1.5 h-1.5 rounded-none bg-[#38e8cb] shadow-[0_0_8px_#38e8cb]" />
                ) : (
                  <IconComponent size={14} className="text-[#5e7083] group-hover:text-[#38e8cb] transition-colors" />
                )}
                <span>{item.label}</span>
              </div>

              {item.badge !== undefined && (
                <span className="px-1.5 py-0.2 rounded-none text-[8.5px] font-mono font-bold bg-[#ff6b6b]/20 text-[#ff6b6b] border border-[#ff6b6b]/40">
                  {item.badge}
                </span>
              )}

              {/* Active Teal Hairline Indicator on Edge */}
              {isActive && (
                <span className="absolute right-0 top-0 bottom-0 w-[2px] bg-[#38e8cb] shadow-[0_0_8px_#38e8cb]" />
              )}
            </button>
          );
        })}
      </div>

      {/* ── Bottom Micro-Label from Stitch Design System ── */}
      <div className="px-6 pt-4 border-t border-[#171e27] flex items-center gap-2 text-[10px] font-mono text-[#5e7083] tracking-[0.2em] uppercase">
        <span className="w-1.5 h-1.5 rounded-none bg-[#38e8cb]" />
        <span>GLOBAL INTELLIGENCE / OPS</span>
      </div>
    </aside>
  );
};
