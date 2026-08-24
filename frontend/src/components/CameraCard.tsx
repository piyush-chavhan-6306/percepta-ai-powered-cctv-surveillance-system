import React, { useState, useRef } from "react";
import type { CameraRecord, CameraDiagnostics } from "../types/surveillance";
import { api } from "../api/client";
import {
  Play,
  Pause,
  Trash2,
  Activity,
  Maximize2,
  Minimize2,
  PenTool,
  Slash,
  Check,
  X,
  AlertCircle,
  ShieldAlert,
  Loader2,
} from "lucide-react";

interface CameraCardProps {
  camera: CameraRecord;
  onRefresh?: () => void;
  onSelect?: (camera: CameraRecord) => void;
  selected?: boolean;
}

export const CameraCard: React.FC<CameraCardProps> = ({
  camera,
  onRefresh,
  onSelect,
  selected = false,
}) => {
  const imgRef = useRef<HTMLImageElement>(null);
  const [isPlaying, setIsPlaying] = useState<boolean>(camera.is_running);
  const [diagnostics, setDiagnostics] = useState<CameraDiagnostics | null>(null);
  const [showDiagModal, setShowDiagModal] = useState<boolean>(false);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [streamError, setStreamError] = useState<boolean>(false);
  const [isActionLoading, setIsActionLoading] = useState<boolean>(false);

  // Drawing state for Task B: Zone & Tripwire in-place creator
  const [drawMode, setDrawMode] = useState<"none" | "polygon" | "tripwire">("none");
  const [points, setPoints] = useState<Array<[number, number]>>([]);
  const [cursorPos, setCursorPos] = useState<[number, number] | null>(null);
  const [zoneName, setZoneName] = useState<string>("");
  const [zoneSeverity, setZoneSeverity] = useState<string>("CRITICAL");
  const [loiteringThreshold, setLoiteringThreshold] = useState<number>(3);
  const [isSavingZone, setIsSavingZone] = useState<boolean>(false);
  const [zoneSuccessMsg, setZoneSuccessMsg] = useState<string | null>(null);

  const streamUrl = api.getVideoStreamUrl(camera.camera_id);

  const handleTogglePlay = async (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsActionLoading(true);
    try {
      if (isPlaying) {
        await api.stopCamera(camera.camera_id);
        setIsPlaying(false);
      } else {
        await api.startCamera(camera.camera_id);
        setIsPlaying(true);
        setStreamError(false);
      }
      onRefresh?.();
    } catch (err) {
      console.error("Failed to toggle camera:", err);
    } finally {
      setIsActionLoading(false);
    }
  };

  const handleDelete = async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (confirm(`Deregister camera ${camera.camera_id} (${camera.name})?`)) {
      setIsActionLoading(true);
      try {
        await api.deleteCamera(camera.camera_id);
        onRefresh?.();
      } catch (err) {
        console.error("Failed to delete camera:", err);
      } finally {
        setIsActionLoading(false);
      }
    }
  };

  const handleFetchDiagnostics = async (e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      const diag = await api.getCameraDiagnostics(camera.camera_id);
      setDiagnostics(diag);
      setShowDiagModal(true);
    } catch (err) {
      console.error("Failed to fetch diagnostics:", err);
    }
  };

  // Convert click coordinates on rendered image to source-frame pixel coordinates
  const handleImageClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (drawMode === "none") return;
    const img = imgRef.current;
    if (!img) return;

    const rect = img.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    // Use naturalWidth/naturalHeight if available, otherwise default standard frame dimensions
    const naturalW = img.naturalWidth || 1920;
    const naturalH = img.naturalHeight || 1080;

    const scaleX = naturalW / rect.width;
    const scaleY = naturalH / rect.height;

    const frameX = Math.round(clickX * scaleX);
    const frameY = Math.round(clickY * scaleY);

    if (drawMode === "tripwire") {
      if (points.length === 0) {
        setPoints([[frameX, frameY]]);
      } else if (points.length === 1) {
        setPoints([...points, [frameX, frameY]]);
      }
    } else if (drawMode === "polygon") {
      setPoints((prev) => [...prev, [frameX, frameY]]);
    }
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (drawMode === "none" || points.length === 0) return;
    const img = imgRef.current;
    if (!img) return;
    const rect = img.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;
    const naturalW = img.naturalWidth || 1920;
    const naturalH = img.naturalHeight || 1080;
    const frameX = Math.round(clickX * (naturalW / rect.width));
    const frameY = Math.round(clickY * (naturalH / rect.height));
    setCursorPos([frameX, frameY]);
  };

  const handleSaveZone = async () => {
    if (drawMode === "polygon" && points.length < 3) {
      alert("A polygon security zone requires at least 3 vertices.");
      return;
    }
    if (drawMode === "tripwire" && points.length < 2) {
      alert("A tripwire boundary requires exactly 2 endpoints.");
      return;
    }

    setIsSavingZone(true);
    try {
      const generatedId = `${drawMode === "polygon" ? "ZONE" : "BND"}_${Date.now().toString().slice(-4)}`;
      const name = zoneName.trim() || `${drawMode === "polygon" ? "Restricted Zone" : "Virtual Boundary"} ${generatedId}`;

      if (drawMode === "polygon") {
        await api.createZone({
          zone_id: generatedId,
          name: name,
          polygon: points,
          severity: zoneSeverity,
          loitering_threshold_seconds: loiteringThreshold,
        });
      } else {
        await api.createBoundary({
          boundary_id: generatedId,
          name: name,
          pt1: points[0],
          pt2: points[1],
          severity: zoneSeverity,
        });
      }

      setZoneSuccessMsg(`Created ${name} (${generatedId})! Applied live.`);
      setDrawMode("none");
      setPoints([]);
      setCursorPos(null);
      setZoneName("");
      setTimeout(() => setZoneSuccessMsg(null), 4000);
      onRefresh?.();
    } catch (err: any) {
      alert(`Failed to save zone: ${err.message}`);
    } finally {
      setIsSavingZone(false);
    }
  };

  const handleCancelDraw = () => {
    setDrawMode("none");
    setPoints([]);
    setCursorPos(null);
  };

  // Convert frame coordinate to percentage for SVG rendering over the image
  const getPct = (pt: [number, number]): { x: number; y: number } => {
    const img = imgRef.current;
    const naturalW = img?.naturalWidth || 1920;
    const naturalH = img?.naturalHeight || 1080;
    return {
      x: (pt[0] / naturalW) * 100,
      y: (pt[1] / naturalH) * 100,
    };
  };

  return (
    <div
      onClick={() => onSelect?.(camera)}
      className={`group relative bg-[#090d14] border transition-all duration-200 rounded-sm overflow-hidden flex flex-col ${
        selected
          ? "border-[#00e5ff] shadow-[0_0_15px_rgba(0,229,255,0.2)]"
          : "border-white/10 hover:border-white/20"
      } ${isExpanded ? "fixed inset-4 z-50 bg-[#05070a]" : "h-full"}`}
    >
      {/* Card Header */}
      <div className="flex items-center justify-between px-3.5 py-2.5 bg-[#0e141f] border-b border-white/10 z-10">
        <div className="flex items-center gap-2.5 min-w-0">
          <span
            className={`w-2 h-2 rounded-full shrink-0 ${
              camera.status === "online"
                ? "bg-[#00e676] animate-pulse"
                : camera.status === "degraded"
                ? "bg-[#ffab00]"
                : "bg-[#ff1744]"
            }`}
          />
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-display font-bold text-sm tracking-wide text-white truncate">
                {camera.name}
              </span>
              <span className="font-mono-tech text-[10px] px-1.5 py-0.5 bg-white/5 border border-white/10 rounded text-gray-300">
                {camera.camera_id}
              </span>
            </div>
            <p className="font-mono-tech text-[10px] text-gray-400 truncate">
              {camera.location_label} • {camera.source_type.toUpperCase()}
            </p>
          </div>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-1.5 shrink-0">
          {/* Draw Zone Trigger */}
          {drawMode === "none" ? (
            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setDrawMode("polygon");
                  setPoints([]);
                }}
                className="px-2 py-1 bg-[#00e5ff]/15 hover:bg-[#00e5ff]/25 text-[#00e5ff] border border-[#00e5ff]/30 text-[10px] font-display font-bold rounded-sm flex items-center gap-1 transition-colors"
                title="Draw restricted polygon security zone on video"
              >
                <PenTool className="w-3 h-3" />
                <span>ZONE</span>
              </button>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  setDrawMode("tripwire");
                  setPoints([]);
                }}
                className="px-2 py-1 bg-[#ffab00]/15 hover:bg-[#ffab00]/25 text-[#ffab00] border border-[#ffab00]/30 text-[10px] font-display font-bold rounded-sm flex items-center gap-1 transition-colors"
                title="Draw directional virtual tripwire on video"
              >
                <Slash className="w-3 h-3" />
                <span>TRIPWIRE</span>
              </button>
            </div>
          ) : null}

          {/* Diagnostics Button */}
          <button
            type="button"
            onClick={handleFetchDiagnostics}
            className="p-1.5 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded-sm transition-colors"
            title="Optical Lens & Sensor Diagnostics"
          >
            <Activity className="w-3.5 h-3.5 text-[#00e5ff]" />
          </button>

          {/* Expand Fullscreen */}
          <button
            type="button"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
            className="p-1.5 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded-sm transition-colors"
            title={isExpanded ? "Collapse video" : "Expand video"}
          >
            {isExpanded ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>

          {/* Start/Stop Camera */}
          <button
            type="button"
            onClick={handleTogglePlay}
            disabled={isActionLoading}
            className={`p-1.5 rounded-sm transition-colors ${
              isPlaying
                ? "bg-amber-500/20 text-amber-400 border border-amber-500/40 hover:bg-amber-500/30"
                : "bg-emerald-500/20 text-emerald-400 border border-emerald-500/40 hover:bg-emerald-500/30"
            }`}
            title={isPlaying ? "Pause perception" : "Resume perception"}
          >
            {isPlaying ? <Pause className="w-3.5 h-3.5" /> : <Play className="w-3.5 h-3.5" />}
          </button>

          {/* Delete Camera */}
          <button
            type="button"
            onClick={handleDelete}
            disabled={isActionLoading}
            className="p-1.5 bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/30 rounded-sm transition-colors"
            title="Deregister camera"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Video / Stream Surface */}
      <div
        onClick={handleImageClick}
        onMouseMove={handleMouseMove}
        className={`relative flex-1 bg-[#05070a] flex items-center justify-center overflow-hidden min-h-[220px] ${
          drawMode !== "none" ? "cursor-crosshair" : "cursor-default"
        }`}
      >
        {isPlaying && !streamError ? (
          <img
            ref={imgRef}
            src={streamUrl}
            alt={camera.name}
            onError={() => setStreamError(true)}
            className="w-full h-full object-contain select-none"
          />
        ) : (
          <div className="flex flex-col items-center justify-center p-6 text-center text-gray-500">
            <AlertCircle className="w-8 h-8 mb-2 text-gray-600" />
            <span className="font-mono-tech text-xs uppercase tracking-wider text-gray-400">
              {streamError ? "SIGNAL LOSS / RECONNECTING" : "FEED PAUSED"}
            </span>
            <span className="text-[10px] text-gray-600 mt-1">
              {streamError ? "Auto-reconnect worker active" : "Press play to resume live perception"}
            </span>
          </div>
        )}

        {/* Real-Time Drawing Overlay Canvas */}
        {drawMode !== "none" && (
          <svg className="absolute inset-0 w-full h-full pointer-events-none z-20">
            {/* Draw Completed Edges */}
            {points.map((pt, i) => {
              if (i === 0) return null;
              const prev = getPct(points[i - 1]);
              const curr = getPct(pt);
              return (
                <line
                  key={`line-${i}`}
                  x1={`${prev.x}%`}
                  y1={`${prev.y}%`}
                  x2={`${curr.x}%`}
                  y2={`${curr.y}%`}
                  stroke={drawMode === "polygon" ? "#00e5ff" : "#ffab00"}
                  strokeWidth="2.5"
                  strokeDasharray={drawMode === "tripwire" ? "6 3" : undefined}
                />
              );
            })}

            {/* Draw Rubberband line to cursor */}
            {cursorPos && points.length > 0 && (
              (() => {
                const last = getPct(points[points.length - 1]);
                const cur = getPct(cursorPos);
                return (
                  <line
                    x1={`${last.x}%`}
                    y1={`${last.y}%`}
                    x2={`${cur.x}%`}
                    y2={`${cur.y}%`}
                    stroke={drawMode === "polygon" ? "rgba(0,229,255,0.6)" : "rgba(255,171,0,0.6)"}
                    strokeWidth="1.5"
                    strokeDasharray="4 4"
                  />
                );
              })()
            )}

            {/* Draw Vertices */}
            {points.map((pt, i) => {
              const p = getPct(pt);
              return (
                <g key={`pt-${i}`}>
                  <circle
                    cx={`${p.x}%`}
                    cy={`${p.y}%`}
                    r="4.5"
                    fill={drawMode === "polygon" ? "#00e5ff" : "#ffab00"}
                    stroke="#ffffff"
                    strokeWidth="1.5"
                  />
                  <text
                    x={`${p.x + 1.5}%`}
                    y={`${p.y - 1.5}%`}
                    fill="#ffffff"
                    fontSize="10"
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    P{i + 1}
                  </text>
                </g>
              );
            })}
          </svg>
        )}

        {/* In-Drawing Controls Ribbon */}
        {drawMode !== "none" && (
          <div
            onClick={(e) => e.stopPropagation()}
            className="absolute top-2 left-2 right-2 z-30 bg-[#0c121d]/95 backdrop-blur-md border border-[#00e5ff]/40 rounded p-2.5 shadow-xl flex items-center justify-between flex-wrap gap-2 text-xs"
          >
            <div className="flex items-center gap-2">
              <span className="font-display font-bold text-[#00e5ff] uppercase">
                {drawMode === "polygon" ? "Draw Polygon Zone" : "Draw Tripwire"}
              </span>
              <span className="font-mono-tech text-[10px] text-gray-400">
                ({points.length} {points.length === 1 ? "point" : "points"} clicked)
              </span>
            </div>

            <div className="flex items-center gap-2">
              <input
                type="text"
                value={zoneName}
                onChange={(e) => setZoneName(e.target.value)}
                placeholder="Zone / Tripwire Name"
                className="bg-[#05070a] border border-white/15 rounded px-2 py-1 text-white text-[11px] font-mono-tech w-36 focus:outline-none focus:border-[#00e5ff]"
              />

              <select
                value={zoneSeverity}
                onChange={(e) => setZoneSeverity(e.target.value)}
                className="bg-[#05070a] border border-white/15 rounded px-2 py-1 text-white text-[11px] font-mono-tech focus:outline-none"
              >
                <option value="CRITICAL">CRITICAL</option>
                <option value="RESTRICTED">RESTRICTED</option>
                <option value="WARNING">WARNING</option>
              </select>

              {drawMode === "polygon" && (
                <div className="flex items-center gap-1 text-[11px] text-gray-400 font-mono-tech" title="Loitering dwell threshold in seconds">
                  <span>Dwell:</span>
                  <input
                    type="number"
                    min="1"
                    max="60"
                    value={loiteringThreshold}
                    onChange={(e) => setLoiteringThreshold(parseInt(e.target.value) || 3)}
                    className="w-10 bg-[#05070a] border border-white/15 rounded px-1 py-0.5 text-center text-white"
                  />
                  <span>s</span>
                </div>
              )}

              <button
                type="button"
                onClick={handleSaveZone}
                disabled={isSavingZone || (drawMode === "polygon" ? points.length < 3 : points.length < 2)}
                className="px-2.5 py-1 bg-[#00e5ff] hover:bg-[#00cce6] text-black font-display font-bold rounded flex items-center gap-1 transition-all disabled:opacity-50"
              >
                {isSavingZone ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />}
                <span>SAVE</span>
              </button>

              <button
                type="button"
                onClick={handleCancelDraw}
                className="px-2 py-1 bg-white/10 hover:bg-white/20 text-gray-300 font-display font-semibold rounded flex items-center gap-1 transition-colors"
              >
                <X className="w-3.5 h-3.5" />
                <span>CANCEL</span>
              </button>
            </div>
          </div>
        )}

        {/* Zone Success Notification Pill */}
        {zoneSuccessMsg && (
          <div className="absolute bottom-3 left-3 right-3 z-30 bg-emerald-500/90 text-black px-3 py-1.5 rounded text-xs font-display font-bold flex items-center gap-2 shadow-lg animate-bounce">
            <Check className="w-4 h-4" />
            <span>{zoneSuccessMsg}</span>
          </div>
        )}

        {/* Tactical Telemetry HUD Strip */}
        <div className="absolute bottom-2 left-2 right-2 flex items-center justify-between pointer-events-none text-[10px] font-mono-tech text-gray-300">
          <div className="flex items-center gap-2 bg-black/60 backdrop-blur-sm px-2 py-0.5 rounded border border-white/10">
            <span className="text-[#00e5ff] font-bold">MJPEG STREAM</span>
            <span>•</span>
            <span>{camera.resolution || "1920x1080"}</span>
          </div>

          <div className="flex items-center gap-2 bg-black/60 backdrop-blur-sm px-2 py-0.5 rounded border border-white/10">
            <span>PERCEPTION:</span>
            <span className="text-[#00e676] font-bold">
              {camera.fps ? camera.fps.toFixed(1) : "30.0"} FPS
            </span>
          </div>
        </div>
      </div>

      {/* Optical Diagnostics Popover Modal */}
      {showDiagModal && diagnostics && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute inset-x-3 bottom-3 z-40 bg-[#0c121d] border border-white/20 rounded p-3 shadow-2xl space-y-2 text-xs"
        >
          <div className="flex items-center justify-between border-b border-white/10 pb-1.5">
            <div className="flex items-center gap-1.5">
              <ShieldAlert className="w-4 h-4 text-[#00e5ff]" />
              <span className="font-display font-bold text-white">
                OPTICAL LENS DIAGNOSTICS • {camera.camera_id}
              </span>
            </div>
            <button
              onClick={() => setShowDiagModal(false)}
              className="text-gray-400 hover:text-white"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>

          <div className="grid grid-cols-4 gap-2 text-[11px] font-mono-tech">
            <div className="bg-black/40 p-1.5 rounded border border-white/5">
              <span className="text-gray-500 block text-[9px]">BLUR SCORE</span>
              <span className="text-white font-bold">{diagnostics.blur_score.toFixed(1)}</span>
            </div>
            <div className="bg-black/40 p-1.5 rounded border border-white/5">
              <span className="text-gray-500 block text-[9px]">BRIGHTNESS</span>
              <span className="text-white font-bold">{diagnostics.brightness_mean.toFixed(1)}</span>
            </div>
            <div className="bg-black/40 p-1.5 rounded border border-white/5">
              <span className="text-gray-500 block text-[9px]">GLARE RATIO</span>
              <span className="text-white font-bold">{(diagnostics.glare_percentage * 100).toFixed(1)}%</span>
            </div>
            <div className="bg-black/40 p-1.5 rounded border border-white/5">
              <span className="text-gray-500 block text-[9px]">DARKNESS</span>
              <span className="text-white font-bold">{(diagnostics.darkness_percentage * 100).toFixed(1)}%</span>
            </div>
          </div>

          <p className="text-[10px] font-mono-tech text-gray-400">
            {diagnostics.diagnosis_message}
          </p>
        </div>
      )}
    </div>
  );
};
