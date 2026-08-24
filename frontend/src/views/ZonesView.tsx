import React, { useState, useRef } from "react";
import { useSurveillance } from "../store/surveillanceContext";
import type { SecurityZone } from "../types/surveillance";
import {
  Shield,
  Plus,
  Trash2,
  CheckCircle2,
  Layers,
  Crosshair,
  Save,
} from "lucide-react";

export const ZonesView: React.FC = () => {
  const { cameras } = useSurveillance();
  const [selectedCameraId, setSelectedCameraId] = useState<string>(cameras[0]?.camera_id || "CAM-01");
  const [zones, setZones] = useState<SecurityZone[]>([
    {
      zone_id: "ZONE_ALPHA_01",
      name: "Restricted Perimeter Zone A",
      polygon: [[15, 20], [85, 20], [85, 75], [15, 75]],
      severity: "critical",
      is_active: true,
      loitering_threshold_seconds: 2.0,
    },
    {
      zone_id: "ZONE_BRAVO_GATE",
      name: "Sector Bravo Convoy Buffer Zone",
      polygon: [[30, 40], [70, 40], [70, 85], [30, 85]],
      severity: "restricted",
      is_active: true,
      loitering_threshold_seconds: 5.0,
    },
  ]);
  const [message, setMessage] = useState<string | null>(null);

  // Drawing state
  const [isDrawing, setIsDrawing] = useState<boolean>(false);
  const [drawnBox, setDrawnBox] = useState<{ x: number; y: number; w: number; h: number } | null>({
    x: 20,
    y: 25,
    w: 60,
    h: 50,
  });
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null);
  const videoContainerRef = useRef<HTMLDivElement>(null);

  // Form State
  const [zoneName, setZoneName] = useState<string>("Sector Alpha — Restricted Zone B");
  const [severity, setSeverity] = useState<string>("critical");
  const [loiterSec, setLoiterSec] = useState<number>(2.5);

  const activeCamera = cameras.find((c) => c.camera_id === selectedCameraId) || cameras[0];

  // Mouse event handlers for interactive zone drawing on video
  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!videoContainerRef.current) return;
    const rect = videoContainerRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
    const y = Math.max(0, Math.min(100, ((e.clientY - rect.top) / rect.height) * 100));
    setDragStart({ x, y });
    setIsDrawing(true);
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isDrawing || !dragStart || !videoContainerRef.current) return;
    const rect = videoContainerRef.current.getBoundingClientRect();
    const currX = Math.max(0, Math.min(100, ((e.clientX - rect.left) / rect.width) * 100));
    const currY = Math.max(0, Math.min(100, ((e.clientY - rect.top) / rect.height) * 100));

    const left = Math.min(dragStart.x, currX);
    const top = Math.min(dragStart.y, currY);
    const width = Math.abs(currX - dragStart.x);
    const height = Math.abs(currY - dragStart.y);

    setDrawnBox({ x: left, y: top, w: width, h: height });
  };

  const handleMouseUp = () => {
    setIsDrawing(false);
    setDragStart(null);
  };

  const handleSaveZone = (e: React.FormEvent) => {
    e.preventDefault();
    if (!drawnBox || drawnBox.w < 5 || drawnBox.h < 5) {
      setMessage("Please draw a valid area rectangle over the video feed.");
      setTimeout(() => setMessage(null), 3000);
      return;
    }

    const newZoneId = `ZONE_${Date.now().toString().slice(-4)}`;
    const newPolygon = [
      [Math.round(drawnBox.x), Math.round(drawnBox.y)],
      [Math.round(drawnBox.x + drawnBox.w), Math.round(drawnBox.y)],
      [Math.round(drawnBox.x + drawnBox.w), Math.round(drawnBox.y + drawnBox.h)],
      [Math.round(drawnBox.x), Math.round(drawnBox.y + drawnBox.h)],
    ];

    const newZone: SecurityZone = {
      zone_id: newZoneId,
      name: zoneName.trim() || `Security Zone ${newZoneId}`,
      polygon: newPolygon,
      severity,
      is_active: true,
      loitering_threshold_seconds: loiterSec,
    };

    setZones((prev) => [newZone, ...prev]);
    setMessage(`Security Zone '${newZone.name}' saved and activated!`);
    setTimeout(() => setMessage(null), 4000);
  };

  const handleDeleteZone = (id: string) => {
    setZones((prev) => prev.filter((z) => z.zone_id !== id));
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-3 flex-wrap gap-2">
        <div className="flex items-center gap-2.5">
          <Shield className="w-5 h-5 text-[#00e5ff]" />
          <div>
            <h2 className="font-display font-bold text-lg tracking-wider text-white">
              SECURITY ZONES & PERIMETER BOUNDARY DESIGNER
            </h2>
            <p className="text-[11px] font-mono-tech text-gray-400">
              Draw interactive geofenced restricted polygons and virtual tripwires directly onto surveillance feeds
            </p>
          </div>
        </div>

        {/* Camera Selector */}
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono-tech text-gray-400">SELECT CCTV FEED:</span>
          <select
            value={selectedCameraId}
            onChange={(e) => setSelectedCameraId(e.target.value)}
            className="select text-xs py-1"
          >
            {cameras.map((c) => (
              <option key={c.camera_id} value={c.camera_id}>
                {c.name} ({c.camera_id})
              </option>
            ))}
          </select>
        </div>
      </div>

      {message && (
        <div className="p-2.5 bg-[#00e676]/15 border border-[#00e676]/30 text-[#00e676] rounded text-xs flex items-center gap-2 font-mono-tech">
          <CheckCircle2 size={16} /> {message}
        </div>
      )}

      {/* Main 2-Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column (7 cols): Interactive Video Feed with Canvas Area Drawer */}
        <div className="lg:col-span-7 flex flex-col gap-3">
          <div className="panel p-3">
            <div className="flex justify-between items-center text-xs font-mono-tech text-gray-400 mb-2">
              <span className="flex items-center gap-1.5 text-white font-bold">
                <Crosshair size={13} color="#00e5ff" />
                CLICK & DRAG TO DEFINE RESTRICTED REGION
              </span>
              <span className="text-[#00e5ff]">
                FEED: {activeCamera?.name || selectedCameraId}
              </span>
            </div>

            {/* Video + Interactive Draw Canvas Container */}
            <div
              ref={videoContainerRef}
              onMouseDown={handleMouseDown}
              onMouseMove={handleMouseMove}
              onMouseUp={handleMouseUp}
              className="relative aspect-video bg-black rounded overflow-hidden border border-white/15 select-none cursor-crosshair"
            >
              <video
                src={activeCamera?.local_video_url || "/videos/border-demo.mp4"}
                autoPlay
                loop
                muted
                playsInline
                className="w-full h-full object-cover pointer-events-none"
              />

              {/* Render Existing Saved Zones as Overlays */}
              {zones.map((z) => (
                <div
                  key={z.zone_id}
                  style={{
                    position: "absolute",
                    left: `${z.polygon[0][0]}%`,
                    top: `${z.polygon[0][1]}%`,
                    width: `${Math.abs(z.polygon[1][0] - z.polygon[0][0])}%`,
                    height: `${Math.abs(z.polygon[2][1] - z.polygon[0][1])}%`,
                    background: z.severity === "critical" ? "rgba(255, 23, 68, 0.15)" : "rgba(255, 171, 0, 0.15)",
                    border: `2px dashed ${z.severity === "critical" ? "#ff1744" : "#ffab00"}`,
                    pointerEvents: "none",
                  }}
                >
                  <span
                    className="text-[9px] font-mono-tech font-bold px-1 py-0.5 rounded text-white absolute top-1 left-1"
                    style={{ background: z.severity === "critical" ? "#ff1744" : "#ffab00" }}
                  >
                    {z.name}
                  </span>
                </div>
              ))}

              {/* Real-time Drawing Box Preview */}
              {drawnBox && (
                <div
                  style={{
                    position: "absolute",
                    left: `${drawnBox.x}%`,
                    top: `${drawnBox.y}%`,
                    width: `${drawnBox.w}%`,
                    height: `${drawnBox.h}%`,
                    border: "2px solid #00e5ff",
                    background: "rgba(0, 229, 255, 0.2)",
                    boxShadow: "0 0 15px rgba(0, 229, 255, 0.5)",
                    pointerEvents: "none",
                  }}
                >
                  <span className="text-[10px] font-mono-tech font-bold bg-[#00e5ff] text-black px-1.5 py-0.2 rounded absolute -top-5 left-0">
                    NEW RESTRICTED ZONE [{Math.round(drawnBox.w)}% × {Math.round(drawnBox.h)}%]
                  </span>
                </div>
              )}

              <div className="absolute bottom-2 left-2 bg-black/70 px-2 py-0.5 rounded text-[10px] font-mono-tech text-gray-300 pointer-events-none">
                DRAG MOUSE OVER VIDEO TO POSITION ZONE
              </div>
            </div>

            <div className="flex justify-between items-center text-[10px] font-mono-tech text-gray-400 mt-2">
              <span>ACTIVE CAMERA: <strong>{activeCamera?.camera_id}</strong></span>
              <span>GEOMETRY: <strong>POINT-IN-POLYGON CONFINEMENT</strong></span>
            </div>
          </div>
        </div>

        {/* Right Column (5 cols): Zone Form & Active Zones List */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          {/* Configure & Save Zone Form */}
          <div className="panel p-4">
            <div className="panel-title text-sm mb-3">
              <Plus size={15} color="#00e5ff" />
              Configure & Activate Security Zone
            </div>

            <form onSubmit={handleSaveZone} className="space-y-3">
              <div>
                <label className="hud-label">Security Zone Name *</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. Sector Alpha — Restricted Perimeter Zone"
                  value={zoneName}
                  onChange={(e) => setZoneName(e.target.value)}
                  className="input text-xs"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="hud-label">Intrusion Severity</label>
                  <select
                    value={severity}
                    onChange={(e) => setSeverity(e.target.value)}
                    className="select text-xs"
                  >
                    <option value="critical">Critical (Immediate Alert)</option>
                    <option value="restricted">Restricted (Warning)</option>
                    <option value="warning">Buffer Zone (Low)</option>
                  </select>
                </div>

                <div>
                  <label className="hud-label">Loiter Threshold</label>
                  <input
                    type="number"
                    step="0.5"
                    min="0.5"
                    max="60"
                    value={loiterSec}
                    onChange={(e) => setLoiterSec(Number(e.target.value))}
                    className="input text-xs"
                  />
                </div>
              </div>

              <button type="submit" className="btn btn-primary btn-sm w-full mt-2" style={{ gap: "0.4rem" }}>
                <Save size={13} /> Save & Apply Security Zone
              </button>
            </form>
          </div>

          {/* Active Security Zones List */}
          <div className="panel p-4 flex-1">
            <div className="panel-title text-sm mb-3">
              <Layers size={15} color="#34d399" />
              Active Security Zones ({zones.length})
            </div>

            <div className="space-y-2 max-h-[260px] overflow-y-auto">
              {zones.map((z) => (
                <div
                  key={z.zone_id}
                  className="p-2.5 bg-[#080c14] border border-white/10 rounded text-xs flex justify-between items-center"
                >
                  <div>
                    <div className="text-white font-bold flex items-center gap-1.5">
                      <span>{z.name}</span>
                      <span
                        className="text-[9px] font-mono-tech px-1.5 py-0.2 rounded font-bold"
                        style={{
                          background: z.severity === "critical" ? "rgba(255,23,68,0.2)" : "rgba(255,171,0,0.2)",
                          color: z.severity === "critical" ? "#ff1744" : "#ffab00",
                        }}
                      >
                        {z.severity.toUpperCase()}
                      </span>
                    </div>
                    <div className="text-[10px] font-mono-tech text-gray-400 mt-0.5">
                      Loiter Threshold: {z.loitering_threshold_seconds}s • Status: ACTIVE
                    </div>
                  </div>

                  <button
                    onClick={() => handleDeleteZone(z.zone_id)}
                    className="btn btn-danger btn-sm"
                    style={{ padding: "0.2rem 0.4rem" }}
                    title="Delete Zone"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
