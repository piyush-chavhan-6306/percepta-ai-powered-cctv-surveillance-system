import React from 'react';
import { useSurveillance } from '../store/surveillanceContext';
import {
  LayoutDashboard,
  Video,
  AlertTriangle,
  Shield,
  Activity,
  FileCheck,
  Cpu,
  Bot,
  Radio,
  Radar,
  Clapperboard,
} from 'lucide-react';

export const Navigation: React.FC = () => {
  const { activeView, setActiveView, alerts, threat, incidents } = useSurveillance();

  const unacknowledgedAlertsCount = alerts.filter((a) => !a.is_acknowledged).length;

  const navSections = [
    {
      label: 'DEMO',
      defaultTab: 'simulation',
      items: [
        {
          id: 'simulation',
          label: 'Live Demo',
          icon: <Radar size={15} />,
          badge: 'MVP',
          badgeStyle: 'bg-[#00e676]/20 text-[#00e676] border border-[#00e676]/40',
        },
        { id: 'landing', label: 'Hero', icon: <Clapperboard size={15} /> },
      ],
    },
    {
      label: 'MISSION',
      defaultTab: 'dashboard',
      items: [
        { id: 'dashboard', label: 'C2 Overview', icon: <LayoutDashboard size={15} /> },
        { id: 'surveillance', label: 'Surveillance Feeds', icon: <Video size={15} /> },
        {
          id: 'threat',
          label: 'Threat Matrix',
          icon: <Activity size={15} />,
          badge: threat?.threat_score ? `${threat.threat_score}` : undefined,
          badgeStyle: 'bg-[#ff1744]/20 text-[#ff1744] border border-[#ff1744]/40',
        },
      ],
    },
    {
      label: 'OPERATIONS',
      defaultTab: 'incidents',
      items: [
        {
          id: 'incidents',
          label: 'Incidents Command',
          icon: <AlertTriangle size={15} />,
          badge: unacknowledgedAlertsCount > 0 ? `${unacknowledgedAlertsCount}` : incidents.length > 0 ? `${incidents.length}` : undefined,
          badgeStyle: 'bg-[#ff1744] text-white font-bold animate-pulse',
        },
        { id: 'zones', label: 'Security Zones', icon: <Shield size={15} /> },
        { id: 'sensors', label: 'Multi-Modal Sensors', icon: <Cpu size={15} /> },
      ],
    },
    {
      label: 'INTELLIGENCE',
      defaultTab: 'intelligence',
      items: [
        { id: 'intelligence', label: 'AI Surveillance Console', icon: <Bot size={15} /> },
        { id: 'forensics', label: 'Evidence & Integrity', icon: <FileCheck size={15} /> },
      ],
    },
  ];

  return (
    <nav className="bg-[#090d14] border-b border-white/10 px-4 py-2 flex items-center justify-between overflow-x-auto shadow-md">
      <div className="flex items-center gap-6">
        {navSections.map((section, sIdx) => (
          <div key={sIdx} className="flex items-center gap-1.5">
            {/* Clickable section header */}
            <button
              onClick={() => setActiveView(section.defaultTab)}
              className="text-[10px] font-mono-tech text-gray-400 hover:text-[#00e5ff] uppercase tracking-widest px-1.5 py-0.5 bg-transparent hover:bg-white/5 rounded cursor-pointer transition-colors"
              title={`Open ${section.label} section`}
            >
              {section.label}
            </button>

            <div className="flex items-center gap-1">
              {section.items.map((tab) => {
                const isActive = activeView === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveView(tab.id)}
                    className={`flex items-center gap-2 px-3 py-1.5 rounded-sm text-xs font-display font-semibold tracking-wider transition-all whitespace-nowrap cursor-pointer ${
                      isActive
                        ? 'bg-[#00e5ff]/15 text-white border border-[#00e5ff]/50 shadow-[0_0_12px_rgba(0,229,255,0.25)]'
                        : 'text-gray-400 hover:text-gray-200 hover:bg-white/5 border border-transparent'
                    }`}
                  >
                    <span className={isActive ? 'text-[#00e5ff]' : 'text-gray-500'}>{tab.icon}</span>
                    <span>{tab.label}</span>
                    {tab.badge && (
                      <span className={`text-[10px] font-mono-tech px-1.5 py-0.2 rounded ${tab.badgeStyle || 'bg-white/10 text-white'}`}>
                        {tab.badge}
                      </span>
                    )}
                  </button>
                );
              })}
            </div>
            {sIdx < navSections.length - 1 && <div className="h-4 w-px bg-white/10 mx-2" />}
          </div>
        ))}
      </div>

      <div className="flex items-center gap-2 text-[11px] font-mono-tech text-gray-400">
        <Radio className="w-3.5 h-3.5 text-[#00e676] animate-pulse" />
        <span className="text-gray-300">C2 BROADCAST: ONLINE</span>
      </div>
    </nav>
  );
};
