import React, { useState, useEffect } from 'react';
import { useSurveillance } from '../store/surveillanceContext';
import { ThreatBadge } from './ThreatBadge';
import { DemoControlModal } from './DemoControlModal';
import {
  Radio,
  Volume2,
  VolumeX,
  RotateCcw,
  RefreshCw,
  Server,
  Shield,
  Maximize2,
  Play,
  Zap,
} from 'lucide-react';

interface HeaderProps {
  onTogglePresentation?: () => void;
}

export const Header: React.FC<HeaderProps> = ({ onTogglePresentation }) => {
  const {
    threat,
    wsStatus,
    audioEnabled,
    setAudioEnabled,
    resetDemo,
    refreshAll,
    coverage,
    metrics,
  } = useSurveillance();

  const [utcTime, setUtcTime] = useState<string>(new Date().toUTCString().slice(17, 25));
  const [isResetting, setIsResetting] = useState(false);
  const [isDemoModalOpen, setIsDemoModalOpen] = useState(false);

  useEffect(() => {
    const timer = setInterval(() => {
      setUtcTime(new Date().toUTCString().slice(17, 25));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const handleReset = async () => {
    if (confirm('Reset live camera pipeline state for a clean judge demonstration?')) {
      setIsResetting(true);
      await resetDemo();
      setIsResetting(false);
    }
  };

  const getWsStatusBadge = () => {
    switch (wsStatus) {
      case 'connected':
        return (
          <span className="flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono-tech font-bold bg-[#00e676]/15 text-[#00e676] border border-[#00e676]/30 rounded">
            <Radio size={11} className="animate-pulse" /> WS LIVE
          </span>
        );
      case 'connecting':
        return (
          <span className="flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono-tech font-bold bg-[#ffab00]/15 text-[#ffab00] border border-[#ffab00]/30 rounded">
            <Radio size={11} className="animate-spin" /> WS CONNECTING
          </span>
        );
      case 'error':
      case 'disconnected':
      default:
        return (
          <span className="flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono-tech font-bold bg-[#ff1744]/15 text-[#ff1744] border border-[#ff1744]/30 rounded">
            <Radio size={11} /> WS OFFLINE
          </span>
        );
    }
  };

  return (
    <>
      <header className="bg-[#080c14] border-b border-white/10 px-4 py-2.5 flex items-center justify-between flex-wrap gap-3 sticky top-0 z-40 backdrop-blur-lg">
        {/* Brand & Mission Title */}
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-br from-[#0284c7] to-[#00e5ff] p-2 rounded-sm shadow-[0_0_12px_rgba(0,229,255,0.35)]">
            <Shield className="w-5 h-5 text-black" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-orbitron font-extrabold text-base tracking-wider text-white">
                BORDER INTELLIGENCE
              </span>
              <span className="text-[10px] font-mono-tech px-1.5 py-0.2 bg-[#00e5ff]/20 text-[#00e5ff] border border-[#00e5ff]/40 rounded font-bold">
                PS SIH26187
              </span>
            </div>
            <div className="text-[10px] font-mono-tech text-gray-400 tracking-wide">
              AI-POWERED PERSISTENT BORDER SURVEILLANCE & INCIDENT INTELLIGENCE
            </div>
          </div>
        </div>

        {/* Telemetry HUD Badges & Action Controls */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* DEFCON Threat Badge */}
          <ThreatBadge level={threat?.threat_level} score={threat?.threat_score} />

          {/* Fleet Readiness */}
          {coverage && (
            <span
              className={`flex items-center gap-1 px-2.5 py-1 text-[11px] font-mono-tech font-bold rounded ${
                coverage.surveillance_readiness_grade === 'GRADE_A_COMBAT_READY'
                  ? 'bg-[#00e676]/15 text-[#00e676] border border-[#00e676]/30'
                  : coverage.surveillance_readiness_grade === 'GRADE_B_DEGRADED'
                  ? 'bg-[#ffab00]/15 text-[#ffab00] border border-[#ffab00]/30'
                  : 'bg-[#ff1744]/15 text-[#ff1744] border border-[#ff1744]/30'
              }`}
            >
              <Server size={11} />
              {coverage.surveillance_readiness_grade.replace('GRADE_', '').replace('_', ' ')} [{coverage.sector_coverage_percentage}%]
            </span>
          )}

          {/* AI Processing Speed */}
          {metrics && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono-tech bg-white/5 text-gray-300 border border-white/10 rounded">
              <Zap size={11} className="text-[#00e5ff]" />
              <span>AI: {metrics.ai_processing_fps.toFixed(1)} FPS</span>
            </span>
          )}

          {/* WebSocket Status */}
          {getWsStatusBadge()}

          {/* UTC Clock */}
          <div className="font-mono-tech text-xs text-gray-300 bg-black/50 px-2.5 py-1 rounded border border-white/10">
            {utcTime} UTC
          </div>

          {/* Audio Chime Toggle */}
          <button
            onClick={() => setAudioEnabled((prev) => !prev)}
            className="p-1.5 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded-sm transition-all"
            title={audioEnabled ? 'Mute alert chimes' : 'Enable alert chimes'}
          >
            {audioEnabled ? <Volume2 size={14} className="text-[#00e676]" /> : <VolumeX size={14} className="text-gray-500" />}
          </button>

          {/* Refresh Telemetry */}
          <button
            onClick={refreshAll}
            className="p-1.5 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded-sm transition-all"
            title="Refresh telemetry"
          >
            <RefreshCw size={14} />
          </button>

          {/* Demo Workflow Guide */}
          <button
            onClick={() => setIsDemoModalOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1 bg-[#00e5ff]/15 hover:bg-[#00e5ff]/25 text-[#00e5ff] border border-[#00e5ff]/40 text-xs font-display font-bold rounded-sm shadow-[0_0_8px_rgba(0,229,255,0.2)]"
          >
            <Play size={12} />
            <span>DEMO WORKFLOW</span>
          </button>

          {/* Presentation Mode */}
          {onTogglePresentation && (
            <button
              onClick={onTogglePresentation}
              className="flex items-center gap-1.5 px-3 py-1 bg-white/10 hover:bg-white/15 text-white border border-white/20 text-xs font-display font-bold rounded-sm"
              title="Enter full-screen judge presentation mode"
            >
              <Maximize2 size={12} className="text-[#00e5ff]" />
              <span>PRESENTATION</span>
            </button>
          )}

          {/* 1-Click Demo Reset */}
          <button
            onClick={handleReset}
            disabled={isResetting}
            className="flex items-center gap-1 px-2.5 py-1 bg-[#ff1744]/15 hover:bg-[#ff1744]/25 text-[#ff1744] border border-[#ff1744]/40 text-xs font-display font-semibold rounded-sm transition-all"
            title="Reset live camera state for demonstration"
          >
            <RotateCcw size={12} />
            <span>{isResetting ? 'Resetting...' : 'Reset'}</span>
          </button>
        </div>
      </header>

      {/* Demo Modal */}
      <DemoControlModal isOpen={isDemoModalOpen} onClose={() => setIsDemoModalOpen(false)} />
    </>
  );
};
