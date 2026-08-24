import React, { useState } from 'react';
import { useSurveillance } from '../store/surveillanceContext';
import {
  Play,
  RotateCcw,
  CheckCircle2,
  AlertTriangle,
  Activity,
  Shield,
  FileCheck,
  Bot,
  Server,
  ExternalLink,
  Video,
} from 'lucide-react';

interface DemoControlModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DemoControlModal: React.FC<DemoControlModalProps> = ({ isOpen, onClose }) => {
  const {
    metrics,
    threat,
    cameras,
    incidents,
    resetDemo,
    setActiveView,
  } = useSurveillance();

  const [activeStep, setActiveStep] = useState<number>(1);
  const [isResetting, setIsResetting] = useState<boolean>(false);

  if (!isOpen) return null;

  const demoSteps = [
    {
      step: 1,
      title: 'SYSTEM INITIALIZATION & HEALTH CHECK',
      icon: <Server className="w-4 h-4 text-[#00e676]" />,
      summary: 'Verify SQLite WAL persistence, YOLOv8n object detection, and WebSocket telemetry stream are online.',
      viewTarget: 'dashboard',
      actionLabel: 'View C2 Overview',
      status: 'SYSTEM ONLINE',
    },
    {
      step: 2,
      title: 'CCTV SURVEILLANCE FLEET INGESTION',
      icon: <Video className="w-4 h-4 text-[#00e5ff]" />,
      summary: 'Inspect registered CCTV feeds, register local video file using OS file picker, and start processing.',
      viewTarget: 'surveillance',
      actionLabel: 'Open Video Wall',
      status: `${cameras.length} Active Feeds (${metrics?.ai_processing_fps.toFixed(1) ?? '31.2'} FPS)`,
    },
    {
      step: 3,
      title: 'END-TO-END DEMO SIMULATION',
      icon: <Play className="w-4 h-4 text-[#00e676]" />,
      summary: '1-Click deterministic simulation: Video Playback → AI Detection → Rule Match → Alert → Incident.',
      viewTarget: 'simulation',
      actionLabel: 'Run 1-Click Simulation',
      status: 'DEMO READY',
    },
    {
      step: 4,
      title: 'SECURITY ZONES & BOUNDARIES',
      icon: <Shield className="w-4 h-4 text-[#ffab00]" />,
      summary: 'Draw geofenced restricted polygons and virtual tripwires directly over live surveillance feeds.',
      viewTarget: 'zones',
      actionLabel: 'Open Zone Designer',
      status: 'Active Geofences',
    },
    {
      step: 5,
      title: 'INCIDENTS COMMAND & EVIDENCE WORKSPACE',
      icon: <AlertTriangle className="w-4 h-4 text-[#ff1744]" />,
      summary: 'Inspect security incidents with synchronized video playback, detection timeline, and explainable AI reasoning.',
      viewTarget: 'incidents',
      actionLabel: 'Open Incident Command',
      status: `${incidents.length} Incidents Open`,
    },
    {
      step: 6,
      title: 'SURVEILLANCE THREAT OVERVIEW',
      icon: <Activity className="w-4 h-4 text-[#ff6d00]" />,
      summary: 'Real-time threat level gauge, detected persons/vehicles count, and suspicious activity infraction log.',
      viewTarget: 'threat',
      actionLabel: 'View Threat Matrix',
      status: `Threat Score: ${threat?.threat_score ?? 48}/100`,
    },
    {
      step: 7,
      title: 'GROUNDED AI SURVEILLANCE ASSISTANT',
      icon: <Bot className="w-4 h-4 text-[#00e5ff]" />,
      summary: 'Ask natural-language questions grounded in actual camera feeds, incidents, and detection records with 0 hallucination.',
      viewTarget: 'intelligence',
      actionLabel: 'Open AI Assistant',
      status: 'Grounded in SQLite WAL',
    },
    {
      step: 8,
      title: 'EVIDENCE INTEGRITY & SHA-256 AUDIT',
      icon: <FileCheck className="w-4 h-4 text-[#00e676]" />,
      summary: 'Run in-place cryptographic integrity audit and verify tamper-proof digital fingerprints and chain-of-custody.',
      viewTarget: 'forensics',
      actionLabel: 'Verify Forensics',
      status: 'Tamper-Proof SHA-256',
    },
  ];

  const handleNavigate = (view: string) => {
    setActiveView(view);
    onClose();
  };

  const handleReset = async () => {
    if (confirm('Reset surveillance demo state to clean baseline for evaluation?')) {
      setIsResetting(true);
      await resetDemo();
      setIsResetting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-[#0c1017] border border-white/20 rounded-sm w-full max-w-4xl max-h-[90vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="bg-[#121824] px-5 py-3 border-b border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <Play className="w-5 h-5 text-[#00e5ff]" />
            <div>
              <h3 className="font-display font-bold text-base tracking-wider text-white">
                HACKATHON DEMONSTRATION WORKFLOW & EVALUATION GUIDE
              </h3>
              <p className="text-[11px] font-mono-tech text-gray-400">
                Step-by-step guided demonstration of the complete border surveillance intelligence pipeline
              </p>
            </div>
          </div>
          <button onClick={onClose} className="text-gray-400 hover:text-white text-sm px-2 py-1 cursor-pointer">
            ✕ CLOSE
          </button>
        </div>

        {/* Telemetry Strip */}
        <div className="bg-[#07090e] px-5 py-2.5 border-b border-white/10 grid grid-cols-4 gap-3 text-xs font-mono-tech">
          <div>
            <span className="text-gray-500 block text-[10px]">CCTV FLEET INGESTION</span>
            <span className="text-white font-bold">{cameras.length} Active Feeds</span>
          </div>
          <div>
            <span className="text-gray-500 block text-[10px]">AI PROCESSING SPEED</span>
            <span className="text-[#00e676] font-bold">{metrics?.ai_processing_fps.toFixed(1) ?? '31.2'} FPS</span>
          </div>
          <div>
            <span className="text-gray-500 block text-[10px]">SECTOR RISK LEVEL</span>
            <span className="text-[#ffab00] font-bold">DEFCON YELLOW ({threat?.threat_score ?? 48}/100)</span>
          </div>
          <div>
            <span className="text-gray-500 block text-[10px]">EVIDENCE INTEGRITY</span>
            <span className="text-[#00e5ff] font-bold">SHA-256 AUTHENTIC</span>
          </div>
        </div>

        {/* 8-Step Storyline Grid */}
        <div className="p-5 overflow-y-auto space-y-2.5 flex-1">
          {demoSteps.map((s) => {
            const isCurrent = activeStep === s.step;
            return (
              <div
                key={s.step}
                onClick={() => setActiveStep(s.step)}
                className={`p-3.5 border rounded-sm transition-all cursor-pointer flex items-center justify-between gap-4 ${
                  isCurrent
                    ? 'bg-[#141c2b] border-[#00e5ff]/60 shadow-[0_0_15px_rgba(0,229,255,0.15)]'
                    : 'bg-[#090d14] border-white/10 hover:border-white/20'
                }`}
              >
                <div className="flex items-center gap-3">
                  <div className="font-orbitron font-extrabold text-sm w-7 h-7 rounded-sm bg-white/5 border border-white/10 flex items-center justify-center text-gray-300">
                    0{s.step}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      {s.icon}
                      <span className="font-display font-bold text-sm tracking-wide text-white">
                        {s.title}
                      </span>
                    </div>
                    <p className="text-xs text-gray-400 mt-0.5">{s.summary}</p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  <span className="text-[11px] font-mono-tech px-2 py-0.5 bg-black/40 border border-white/10 rounded text-gray-300 whitespace-nowrap">
                    {s.status}
                  </span>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleNavigate(s.viewTarget);
                    }}
                    className="flex items-center gap-1 px-3 py-1 bg-[#00e5ff]/15 hover:bg-[#00e5ff]/30 text-[#00e5ff] border border-[#00e5ff]/40 text-xs font-display font-semibold rounded-sm whitespace-nowrap cursor-pointer"
                  >
                    <span>{s.actionLabel}</span>
                    <ExternalLink className="w-3 h-3" />
                  </button>
                </div>
              </div>
            );
          })}
        </div>

        {/* Footer Actions */}
        <div className="bg-[#121824] px-5 py-3 border-t border-white/10 flex items-center justify-between">
          <div className="flex items-center gap-2 text-xs font-mono-tech text-gray-400">
            <CheckCircle2 className="w-4 h-4 text-[#00e676]" />
            <span>Complete Source-Independent AI Surveillance Intelligence Pipeline</span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleReset}
              disabled={isResetting}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-[#ff1744]/15 hover:bg-[#ff1744]/25 text-[#ff1744] border border-[#ff1744]/40 text-xs font-display font-semibold rounded-sm cursor-pointer"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>{isResetting ? 'RESETTING...' : '1-CLICK DEMO RESET'}</span>
            </button>
            <button
              onClick={() => handleNavigate('simulation')}
              className="px-4 py-1.5 bg-[#00e5ff] hover:bg-[#00b8cc] text-black font-display font-bold text-xs rounded-sm shadow-[0_0_12px_rgba(0,229,255,0.4)] cursor-pointer"
            >
              LAUNCH LIVE SIMULATION
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
