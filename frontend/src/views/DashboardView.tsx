import React, { useState } from "react";
import { useSurveillance } from "../store/surveillanceContext";
import { CameraCard } from "../components/CameraCard";
import {
  Grid2X2,
  Grid3X3,
  Square,
  AlertTriangle,
  Check,
  Radio,
  Plus,
  RefreshCw,
} from "lucide-react";

export const DashboardView: React.FC = () => {
  const {
    cameras,
    alerts,
    acknowledgeAlert,
    refreshAll,
  } = useSurveillance();

  const [layout, setLayout] = useState<"single" | "grid2" | "grid3">("grid2");
  const [selectedCameraId, setSelectedCameraId] = useState<string | null>(
    cameras[0]?.camera_id || null
  );

  const displayedCameras =
    layout === "single" && selectedCameraId
      ? cameras.filter((c) => c.camera_id === selectedCameraId)
      : cameras;

  const unacknowledgedAlerts = alerts.filter((a) => !a.is_acknowledged);

  return (
    <div className="space-y-4">
      {/* Top Operations Action Bar */}
      <div className="flex items-center justify-between flex-wrap gap-3 bg-[#0a0f18] border border-white/10 p-3 rounded-sm">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 bg-[#060910] p-1 rounded border border-white/10">
            <button
              onClick={() => setLayout("single")}
              className={`p-1.5 rounded transition-all ${
                layout === "single"
                  ? "bg-[#00e5ff] text-black"
                  : "text-gray-400 hover:text-white"
              }`}
              title="Single Focused Feed (1x1)"
            >
              <Square className="w-4 h-4" />
            </button>
            <button
              onClick={() => setLayout("grid2")}
              className={`p-1.5 rounded transition-all ${
                layout === "grid2"
                  ? "bg-[#00e5ff] text-black"
                  : "text-gray-400 hover:text-white"
              }`}
              title="Quad Grid Layout (2x2)"
            >
              <Grid2X2 className="w-4 h-4" />
            </button>
            <button
              onClick={() => setLayout("grid3")}
              className={`p-1.5 rounded transition-all ${
                layout === "grid3"
                  ? "bg-[#00e5ff] text-black"
                  : "text-gray-400 hover:text-white"
              }`}
              title="Matrix Grid Layout (3x3)"
            >
              <Grid3X3 className="w-4 h-4" />
            </button>
          </div>

          {/* Camera Selector Pills */}
          <div className="flex items-center gap-1.5 overflow-x-auto max-w-md">
            {cameras.map((c) => (
              <button
                key={c.camera_id}
                onClick={() => {
                  setSelectedCameraId(c.camera_id);
                  if (layout === "single") setLayout("single");
                }}
                className={`px-2.5 py-1 text-[11px] font-mono-tech font-bold rounded flex items-center gap-1.5 transition-all whitespace-nowrap ${
                  selectedCameraId === c.camera_id
                    ? "bg-[#00e5ff]/20 text-[#00e5ff] border border-[#00e5ff]/50"
                    : "bg-white/5 text-gray-400 border border-white/10 hover:text-white"
                }`}
              >
                <span
                  className={`w-1.5 h-1.5 rounded-full ${
                    c.status === "online" ? "bg-[#00e676]" : "bg-[#ff1744]"
                  }`}
                />
                <span>{c.camera_id}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Live Status Indicators */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 font-mono-tech text-xs text-gray-300">
            <Radio className="w-3.5 h-3.5 text-[#00e676] animate-pulse" />
            <span>
              LIVE PERCEPTION: <strong>{cameras.filter((c) => c.is_running).length}/{cameras.length}</strong> ACTIVE
            </span>
          </div>

          <button
            onClick={refreshAll}
            className="p-1.5 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded transition-colors"
            title="Refresh All Feeds"
          >
            <RefreshCw className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Main Operations Grid Layout (Video Feeds Left + Live Alerts Right) */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column (8 or 9 cols): Live Video Feeds */}
        <div className="col-span-12 lg:col-span-8 space-y-4">
          {displayedCameras.length > 0 ? (
            <div
              className={`grid gap-4 ${
                layout === "single"
                  ? "grid-cols-1"
                  : layout === "grid2"
                  ? "grid-cols-1 md:grid-cols-2"
                  : "grid-cols-1 md:grid-cols-2 lg:grid-cols-3"
              }`}
            >
              {displayedCameras.map((camera) => (
                <div key={camera.camera_id} className="min-h-[320px]">
                  <CameraCard
                    camera={camera}
                    selected={selectedCameraId === camera.camera_id}
                    onSelect={(cam) => setSelectedCameraId(cam.camera_id)}
                    onRefresh={refreshAll}
                  />
                </div>
              ))}
            </div>
          ) : (
            <div className="flex flex-col items-center justify-center p-12 bg-[#090d14] border border-white/10 rounded-sm text-center">
              <AlertTriangle className="w-10 h-10 text-[#ffab00] mb-3" />
              <h4 className="font-display font-bold text-base text-white mb-1">
                NO SURVEILLANCE CAMERAS CONFIGURED
              </h4>
              <p className="text-xs text-gray-400 font-mono-tech max-w-sm mb-4">
                Add a bundled VIRAT video clip, your laptop webcam, or an RTSP stream to start live perception.
              </p>
              <button
                onClick={refreshAll}
                className="px-4 py-2 bg-[#00e5ff] hover:bg-[#00cce6] text-black font-display font-bold text-xs rounded flex items-center gap-1.5"
              >
                <Plus className="w-4 h-4" />
                <span>LOAD CAMERA FLEET</span>
              </button>
            </div>
          )}
        </div>

        {/* Right Column (4 cols): Live Real-Time Alert Stream */}
        <div className="col-span-12 lg:col-span-4 flex flex-col bg-[#090d14] border border-white/10 rounded-sm overflow-hidden min-h-[500px]">
          {/* Alerts Header */}
          <div className="flex items-center justify-between px-4 py-3 bg-[#0e141f] border-b border-white/10">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-4 h-4 text-[#ff1744]" />
              <h3 className="font-display font-bold text-sm tracking-wide text-white">
                LIVE PERIMETER ALERTS
              </h3>
            </div>
            <span
              className={`text-[10px] font-mono-tech font-bold px-2 py-0.5 rounded ${
                unacknowledgedAlerts.length > 0
                  ? "bg-[#ff1744]/20 text-[#ff1744] border border-[#ff1744]/40 animate-pulse"
                  : "bg-white/5 text-gray-400 border border-white/10"
              }`}
            >
              {unacknowledgedAlerts.length} UNACKNOWLEDGED
            </span>
          </div>

          {/* Alerts Scrollable Stream */}
          <div className="flex-1 p-3 overflow-y-auto space-y-2.5 max-h-[680px]">
            {alerts.length > 0 ? (
              alerts.map((alert) => {
                const isCritical = alert.severity?.toUpperCase() === "CRITICAL";
                const isRestricted = alert.severity?.toUpperCase() === "RESTRICTED";
                const isAck = alert.is_acknowledged;

                return (
                  <div
                    key={alert.event_id}
                    className={`p-3 rounded border transition-all flex flex-col gap-2 ${
                      isAck
                        ? "bg-[#060910] border-white/5 opacity-60"
                        : isCritical
                        ? "bg-[#180b0e] border-red-500/40 shadow-[0_0_10px_rgba(255,23,68,0.15)]"
                        : isRestricted
                        ? "bg-[#161208] border-amber-500/40"
                        : "bg-[#0c121d] border-white/10"
                    }`}
                  >
                    <div className="flex items-center justify-between text-[11px] font-mono-tech">
                      <div className="flex items-center gap-1.5">
                        <span
                          className={`px-1.5 py-0.2 rounded font-bold uppercase text-[9px] ${
                            isCritical
                              ? "bg-red-500/20 text-red-400 border border-red-500/30"
                              : isRestricted
                              ? "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                              : "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                          }`}
                        >
                          {alert.severity}
                        </span>
                        <span className="text-gray-300 font-bold">{alert.camera_id}</span>
                        {alert.track_id && (
                          <span className="text-gray-400">TRK-{alert.track_id}</span>
                        )}
                      </div>

                      <span className="text-gray-500 text-[10px]">
                        {new Date(alert.timestamp).toLocaleTimeString()}
                      </span>
                    </div>

                    <p className="text-xs text-gray-200 font-sans leading-snug">
                      {alert.message}
                    </p>

                    {!isAck && (
                      <div className="flex items-center justify-end pt-1">
                        <button
                          type="button"
                          onClick={() => acknowledgeAlert(alert.event_id)}
                          className="px-2.5 py-1 bg-white/5 hover:bg-white/15 text-gray-300 text-[10px] font-mono-tech font-semibold rounded flex items-center gap-1 border border-white/10 transition-colors"
                        >
                          <Check className="w-3 h-3 text-[#00e676]" />
                          <span>ACKNOWLEDGE</span>
                        </button>
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="flex flex-col items-center justify-center p-8 text-center text-gray-500 font-mono-tech text-xs">
                <Check className="w-6 h-6 text-[#00e676] mb-2" />
                <span>ALL SECTORS CLEAR</span>
                <span className="text-[10px] text-gray-600 mt-0.5">
                  No active boundary or zone breaches.
                </span>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
