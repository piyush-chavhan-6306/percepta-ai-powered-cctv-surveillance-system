import React, { useState, useEffect } from "react";
import { useSurveillance } from "../store/surveillanceContext";
import { AddCameraModal } from "./AddCameraModal";
import {
  Shield,
  Radio,
  Volume2,
  VolumeX,
  Plus,
  RefreshCw,
  Zap,
  Server,
} from "lucide-react";

export const Header: React.FC = () => {
  const {
    wsStatus,
    audioEnabled,
    setAudioEnabled,
    refreshAll,
    metrics,
    coverage,
    registerCameraLocally,
  } = useSurveillance();

  const [utcTime, setUtcTime] = useState<string>(new Date().toUTCString().slice(17, 25));
  const [isAddModalOpen, setIsAddModalOpen] = useState<boolean>(false);

  useEffect(() => {
    const timer = setInterval(() => {
      setUtcTime(new Date().toUTCString().slice(17, 25));
    }, 1000);
    return () => clearInterval(timer);
  }, []);

  const getWsBadge = () => {
    switch (wsStatus) {
      case "connected":
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-mono-tech font-bold bg-[#00e676]/15 text-[#00e676] border border-[#00e676]/30 rounded">
            <Radio size={11} className="animate-pulse" /> WS LIVE
          </span>
        );
      case "connecting":
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-mono-tech font-bold bg-[#ffab00]/15 text-[#ffab00] border border-[#ffab00]/30 rounded">
            <Radio size={11} className="animate-spin" /> WS CONNECTING
          </span>
        );
      case "error":
      case "disconnected":
      default:
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 text-[10px] font-mono-tech font-bold bg-[#ff1744]/15 text-[#ff1744] border border-[#ff1744]/30 rounded">
            <Radio size={11} /> WS OFFLINE
          </span>
        );
    }
  };

  return (
    <>
      <header className="bg-[#080c14] border-b border-white/10 px-5 py-2.5 flex items-center justify-between flex-wrap gap-3 sticky top-0 z-40 backdrop-blur-md">
        {/* Brand & Identity */}
        <div className="flex items-center gap-3">
          <div className="bg-gradient-to-br from-[#0284c7] to-[#00e5ff] p-2 rounded-sm shadow-[0_0_12px_rgba(0,229,255,0.35)]">
            <Shield className="w-5 h-5 text-black" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-orbitron font-extrabold text-base tracking-wider text-white">
                BORDER INTELLIGENCE
              </span>
              <span className="text-[10px] font-mono-tech px-1.5 py-0.5 bg-[#00e5ff]/15 text-[#00e5ff] border border-[#00e5ff]/30 rounded font-bold">
                SIH26187
              </span>
            </div>
            <div className="text-[10px] font-mono-tech text-gray-400">
              REAL-TIME AI BORDER SURVEILLANCE & PERIMETER DEFENSE PLATFORM
            </div>
          </div>
        </div>

        {/* Telemetry & Controls */}
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Measured AI Perception FPS */}
          {metrics && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono-tech bg-white/5 text-gray-300 border border-white/10 rounded">
              <Zap size={11} className="text-[#00e5ff]" />
              <span>AI: {metrics.ai_processing_fps.toFixed(1)} FPS</span>
              <span className="text-gray-500">•</span>
              <span className="text-gray-400">{metrics.inference_latency_ms.toFixed(0)}ms</span>
            </span>
          )}

          {/* Fleet Status */}
          {coverage && (
            <span className="flex items-center gap-1.5 px-2.5 py-1 text-[11px] font-mono-tech bg-white/5 text-gray-300 border border-white/10 rounded">
              <Server size={11} className="text-[#00e676]" />
              <span>FLEET: {coverage.active_cameras_online} ONLINE</span>
            </span>
          )}

          {/* WebSocket Status */}
          {getWsBadge()}

          {/* Clock */}
          <div className="font-mono-tech text-xs text-gray-300 bg-black/50 px-2.5 py-1 rounded border border-white/10">
            {utcTime} UTC
          </div>

          {/* Audio Chimes */}
          <button
            type="button"
            onClick={() => setAudioEnabled((prev) => !prev)}
            className="p-1.5 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded-sm transition-all"
            title={audioEnabled ? "Mute alert chimes" : "Enable alert chimes"}
          >
            {audioEnabled ? <Volume2 size={14} className="text-[#00e676]" /> : <VolumeX size={14} className="text-gray-500" />}
          </button>

          {/* Refresh */}
          <button
            type="button"
            onClick={refreshAll}
            className="p-1.5 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded-sm transition-all"
            title="Refresh telemetry"
          >
            <RefreshCw size={14} />
          </button>

          {/* Add Camera Button */}
          <button
            type="button"
            onClick={() => setIsAddModalOpen(true)}
            className="px-3 py-1.5 bg-[#00e5ff] hover:bg-[#00cce6] text-black font-display font-bold text-xs rounded-sm flex items-center gap-1.5 transition-all shadow-[0_0_10px_rgba(0,229,255,0.3)]"
          >
            <Plus size={13} />
            <span>ADD CAMERA</span>
          </button>
        </div>
      </header>

      {/* Add Camera Modal */}
      <AddCameraModal
        isOpen={isAddModalOpen}
        onClose={() => setIsAddModalOpen(false)}
        onCameraAdded={(newCam) => {
          registerCameraLocally(newCam);
          refreshAll();
        }}
      />
    </>
  );
};
