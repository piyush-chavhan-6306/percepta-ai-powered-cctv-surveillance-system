import React from 'react';
import { useSurveillance } from '../store/surveillanceContext';
import { TacticalMap3D } from './TacticalMap3D';
import { ThreatGauge } from './ThreatGauge';
import { AlertTicker } from './AlertTicker';
import { CameraCard } from './CameraCard';
import {
  Eye,
  Minimize2,
  Zap,
  Server,
  Layers,
} from 'lucide-react';

interface PresentationModeProps {
  onExit: () => void;
}

export const PresentationMode: React.FC<PresentationModeProps> = ({ onExit }) => {
  const {
    cameras,
    threat,
    metrics,
    coverage,
    alerts,
    refreshAll,
  } = useSurveillance();

  const primaryCamera = cameras[0];

  return (
    <div className="fixed inset-0 z-50 bg-[#05070a] text-white flex flex-col p-4 overflow-hidden tactical-grid-bg">
      {/* Top Presentation HUD Bar */}
      <header className="flex items-center justify-between border-b border-white/15 pb-3 mb-4 bg-[#0c1017]/80 backdrop-blur-md px-4 py-2.5 rounded-sm">
        <div className="flex items-center gap-3">
          <div className="w-3 h-3 rounded-full bg-[#00e676] animate-ping"></div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-orbitron font-extrabold text-lg tracking-wider text-white">
                BORDER INTELLIGENCE
              </span>
              <span className="text-[10px] font-mono-tech px-2 py-0.5 bg-[#00e5ff]/20 text-[#00e5ff] border border-[#00e5ff]/40 rounded font-bold">
                DEFENSE COMMAND THEATER • PS SIH26187
              </span>
            </div>
            <p className="text-xs font-mono-tech text-gray-400">
              AI-Powered Persistent Border Surveillance & Incident Intelligence Platform
            </p>
          </div>
        </div>

        {/* Presentation Telemetry HUD */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs font-mono-tech px-3 py-1 bg-black/40 border border-white/10 rounded">
            <Zap className="w-3.5 h-3.5 text-[#00e5ff]" />
            <span>AI PERCEPTION: <strong className="text-[#00e5ff]">{metrics?.ai_processing_fps.toFixed(1) ?? '31.2'} FPS</strong></span>
          </div>

          <div className="flex items-center gap-2 text-xs font-mono-tech px-3 py-1 bg-black/40 border border-white/10 rounded">
            <Server className="w-3.5 h-3.5 text-[#00e676]" />
            <span>FLEET: <strong className="text-[#00e676]">{coverage?.surveillance_readiness_grade?.replace('GRADE_', '').replace('_', ' ') ?? 'COMBAT READY'}</strong></span>
          </div>

          <div className="flex items-center gap-2 text-xs font-mono-tech px-3 py-1 bg-black/40 border border-white/10 rounded">
            <Layers className="w-3.5 h-3.5 text-[#2979ff]" />
            <span>TARGETS: <strong className="text-white">{metrics?.active_tracks ?? 0} CENTROIDS</strong></span>
          </div>

          <button
            onClick={onExit}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-white/10 hover:bg-white/20 text-gray-200 border border-white/20 text-xs font-display font-semibold rounded-sm transition-all"
          >
            <Minimize2 className="w-3.5 h-3.5" />
            <span>EXIT THEATER</span>
          </button>
        </div>
      </header>

      {/* Main Presentation Grid */}
      <div className="grid grid-cols-12 gap-4 flex-1 overflow-hidden">
        {/* Left Column (7 cols): Live CCTV Stream + Real-Time Telemetry */}
        <div className="col-span-7 flex flex-col gap-4">
          {/* Featured Video Feed */}
          <div className="flex-1 bg-[#090d14] border border-white/15 rounded-sm p-3 flex flex-col justify-between">
            <div className="flex items-center justify-between border-b border-white/10 pb-2 mb-2">
              <div className="flex items-center gap-2">
                <Eye className="w-4 h-4 text-[#00e5ff]" />
                <span className="font-display font-bold text-sm text-white">
                  LIVE CCTV SURVEILLANCE FEED • {primaryCamera?.name ?? 'SECTOR ALPHA'}
                </span>
              </div>
              <span className="text-[10px] font-mono-tech px-2 py-0.5 bg-[#00e676]/20 text-[#00e676] border border-[#00e676]/30 rounded font-bold">
                STREAMING MJPEG
              </span>
            </div>

            {primaryCamera ? (
              <div className="flex-1 flex items-center justify-center overflow-hidden">
                <CameraCard camera={primaryCamera} onRefresh={refreshAll} />
              </div>
            ) : (
              <div className="flex-1 flex items-center justify-center text-gray-500 font-mono-tech text-xs">
                No active camera registered.
              </div>
            )}
          </div>
        </div>

        {/* Right Column (5 cols): 3D Situation Map + DEFCON Gauge + Alerts */}
        <div className="col-span-5 flex flex-col gap-4">
          {/* 3D Map */}
          <div className="h-[280px] w-full">
            <TacticalMap3D
              cameras={cameras}
              zones={[]}
              boundaries={[]}
              alerts={alerts}
              selectedCameraId={primaryCamera?.camera_id ?? null}
              onSelectCamera={() => {}}
            />
          </div>

          {/* Bottom Split: DEFCON Gauge & Alert Stream */}
          <div className="grid grid-cols-2 gap-3 flex-1">
            <div className="h-full">
              <ThreatGauge threat={threat} />
            </div>
            <div className="h-full">
              <AlertTicker limit={6} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
