import { useState, useRef, useEffect, useMemo, MouseEvent } from "react";
import { api, API_BASE_URL } from "@/api/client";
import { SecurityZone, VirtualBoundary } from "@/types/surveillance";
import {
  useDisplayedImageRect,
  clickToFrameCoords,
} from "@/hooks/useDisplayedImageRect";
import {
  Square,
  Crosshair,
  Trash2,
  Check,
  X,
  Camera,
  Shield,
  Zap,
  Undo2,
  Play,
  Pause,
  RotateCcw,
  Radio,
  Eye,
  Flame,
  Moon,
  Video,
  Clock,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

interface CameraFeedProps {
  cameraId: string;
  cameraName?: string;
  modality?: "STANDARD" | "IR_NIGHT" | "THERMAL" | string;
  selectedAlertTime?: string | number | null;
  isRunning?: boolean;
  onToggleRun?: () => void;
  onExitSeek?: () => void;
  onZoneCreated?: () => void;
}

type DrawMode = "none" | "polygon" | "tripwire";

export function CameraFeed({
  cameraId,
  cameraName = "Border Sector Feed",
  modality = "STANDARD",
  selectedAlertTime = null,
  isRunning = true,
  onToggleRun,
  onExitSeek,
  onZoneCreated,
}: CameraFeedProps) {
  const [activeModality, setActiveModality] = useState<string>(modality);
  const [drawMode, setDrawMode] = useState<DrawMode>("none");
  const [points, setPoints] = useState<[number, number][]>([]);
  const [cursor, setCursor] = useState<[number, number] | null>(null);
  const [zones, setZones] = useState<SecurityZone[]>([]);
  const [boundaries, setBoundaries] = useState<VirtualBoundary[]>([]);
  const [zoneName, setZoneName] = useState("");
  const [severity, setSeverity] = useState<string>("restricted");
  const [tripwireDirection, setTripwireDirection] = useState<string>("BIDIRECTIONAL");
  const [isSaving, setIsSaving] = useState(false);
  const [frozenAt, setFrozenAt] = useState<number>(0);
  const [selectedTriggerId, setSelectedTriggerId] = useState<string>("");
  const [isDeletingTrigger, setIsDeletingTrigger] = useState(false);

  // Timeline Seek State
  const [isReplaying, setIsReplaying] = useState(false);
  const [seekOffsetSec, setSeekOffsetSec] = useState<number>(0); // -5s to +5s
  const isSeekMode = selectedAlertTime !== null;

  const selectedTrigger = useMemo(() => {
    if (!selectedTriggerId) return null;
    const z = zones.find((item) => item.zone_id === selectedTriggerId);
    if (z) {
      return {
        id: z.zone_id,
        name: z.name,
        type: "ZONE" as const,
        severity: (z.severity || "RESTRICTED").toUpperCase(),
        direction: undefined,
      };
    }
    const b = boundaries.find((item) => item.boundary_id === selectedTriggerId);
    if (b) {
      return {
        id: b.boundary_id,
        name: b.name,
        type: "TRIPWIRE" as const,
        severity: (b.severity || "CRITICAL").toUpperCase(),
        direction: b.direction || "BIDIRECTIONAL",
      };
    }
    return null;
  }, [selectedTriggerId, zones, boundaries]);

  const imageRef = useRef<HTMLImageElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const { rect, remeasure } = useDisplayedImageRect(imageRef);

  const isDrawing = drawMode !== "none";
  const required = drawMode === "tripwire" ? 2 : 3;
  const canSave = points.length >= required;

  const containerRect = containerRef.current?.getBoundingClientRect();
  const svgLeft = rect.ready && containerRect ? (rect.elementLeft - containerRect.left) + rect.offsetX : rect.offsetX;
  const svgTop = rect.ready && containerRect ? (rect.elementTop - containerRect.top) + rect.offsetY : rect.offsetY;

  useEffect(() => {
    setActiveModality(modality);
  }, [modality]);

  useEffect(() => {
    if (selectedAlertTime) {
      setSeekOffsetSec(0);
      setIsReplaying(true);
    }
  }, [selectedAlertTime]);

  const fetchZones = async () => {
    try {
      const res = await api.getZones();
      setZones(res.zones || []);
      setBoundaries(res.boundaries || []);
    } catch (err) {
      console.error("Failed to fetch zones:", err);
    }
  };

  useEffect(() => {
    fetchZones();
  }, [cameraId]);

  const beginDraw = (mode: DrawMode) => {
    setDrawMode(mode);
    setPoints([]);
    setCursor(null);
    setZoneName("");
    setSeverity(mode === "tripwire" ? "critical" : "restricted");
    setTripwireDirection("BIDIRECTIONAL");
    setFrozenAt(Date.now());
  };

  const cancelDraw = () => {
    setDrawMode("none");
    setPoints([]);
    setCursor(null);
  };

  const undoPoint = () => setPoints((prev) => prev.slice(0, -1));

  useEffect(() => {
    if (!isDrawing) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        cancelDraw();
      } else if (e.key === "Backspace" || e.key === "Delete") {
        e.preventDefault();
        undoPoint();
      } else if (e.key === "Enter" && canSave) {
        e.preventDefault();
        void handleSaveZone();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [isDrawing, canSave, points, zoneName, severity, drawMode]);

  const handleClick = (e: MouseEvent<HTMLDivElement>) => {
    if (!isDrawing || !rect) return;
    const pt = clickToFrameCoords(e.clientX, e.clientY, rect);
    if (!pt) return;

    if (drawMode === "tripwire") {
      if (points.length === 0) setPoints([pt]);
      else if (points.length === 1) setPoints([points[0], pt]);
    } else {
      setPoints((prev) => [...prev, pt]);
    }
  };

  const handleMouseMove = (e: MouseEvent<HTMLDivElement>) => {
    if (!isDrawing || !rect) return;
    const pt = clickToFrameCoords(e.clientX, e.clientY, rect);
    setCursor(pt);
  };

  const handleSaveZone = async () => {
    if (!canSave) return;
    setIsSaving(true);
    try {
      const name = zoneName.trim() || `${drawMode.toUpperCase()} #${Date.now().toString().slice(-4)}`;
      if (drawMode === "polygon") {
        await api.createZone({
          name,
          polygon: points,
          severity,
        });
      } else if (drawMode === "tripwire" && points.length >= 2) {
        await api.createBoundary({
          name,
          pt1: points[0],
          pt2: points[1],
          severity,
          direction: tripwireDirection,
        });
      }
      cancelDraw();
      setZoneName("");
      await fetchZones();
      onZoneCreated?.();
    } catch (err) {
      console.error("Failed to save zone:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteTrigger = async () => {
    if (!selectedTriggerId) return;
    setIsDeletingTrigger(true);
    try {
      await api.deleteZone(selectedTriggerId);
      setSelectedTriggerId("");
      await fetchZones();
      onZoneCreated?.();
    } catch (err) {
      console.error("Failed to delete trigger:", err);
    } finally {
      setIsDeletingTrigger(false);
    }
  };

  const [streamEpoch, setStreamEpoch] = useState<number>(Date.now());

  useEffect(() => {
    if (isRunning) {
      setStreamEpoch(Date.now());
    }
  }, [isRunning, cameraId]);

  const feedUrl = useMemo(() => {
    if (isDrawing && frozenAt) {
      return `${API_BASE_URL}/api/streaming/snapshot/${cameraId}?t=${frozenAt}`;
    }
    if (isSeekMode && selectedAlertTime) {
      return `${API_BASE_URL}/api/streaming/replay/${cameraId}?timestamp=${encodeURIComponent(String(selectedAlertTime))}&offset_sec=${seekOffsetSec}&t=${streamEpoch}`;
    }
    if (!isRunning) {
      return "";
    }
    return `${API_BASE_URL}/api/streaming/feed/${cameraId}?t=${streamEpoch}`;
  }, [cameraId, isDrawing, frozenAt, isRunning, streamEpoch, isSeekMode, selectedAlertTime, seekOffsetSec]);

  const modalityBadge = useMemo(() => {
    switch (activeModality.toUpperCase()) {
      case "IR_NIGHT":
      case "IR":
        return {
          label: "IR NIGHT VISION",
          icon: Moon,
          color: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
        };
      case "THERMAL":
        return {
          label: "THERMAL SURVEILLANCE",
          icon: Flame,
          color: "bg-orange-500/20 text-orange-300 border-orange-500/40",
        };
      default:
        return {
          label: "OPTICAL RGB",
          icon: Video,
          color: "bg-cyan-500/20 text-cyan-300 border-cyan-500/40",
        };
    }
  }, [activeModality]);

  const IconComp = modalityBadge.icon;

  return (
    <div className="flex flex-col h-full overflow-hidden relative">
      {/* Top Telemetry Header */}
      <div className="px-4 py-3 border-b border-white/10 flex items-center justify-between bg-black/40">
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
            <h2 className="text-xs font-bold text-foreground font-mono uppercase tracking-wider">
              {cameraId} — {cameraName}
            </h2>
          </div>

          {/* Modality Badge */}
          <Badge
            variant="outline"
            className={`text-[10px] font-mono px-2 py-0.5 flex items-center gap-1 uppercase ${modalityBadge.color}`}
          >
            <IconComp className="w-3 h-3" />
            {modalityBadge.label}
          </Badge>

          {isSeekMode && (
            <Badge
              variant="destructive"
              className="text-[10px] font-mono px-2 py-0.5 bg-red-600/30 text-red-300 border-red-500/50 flex items-center gap-1 animate-pulse"
            >
              <Clock className="w-3 h-3" /> FORENSIC REPLAY MODE
            </Badge>
          )}
        </div>

        {/* Toolbar Controls */}
        <div className="flex items-center gap-2">
          {/* Modality Switcher */}
          <div className="flex items-center bg-black/50 border border-white/10 rounded-lg p-0.5 text-[10px] font-mono">
            {(["STANDARD", "IR_NIGHT", "THERMAL"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setActiveModality(m)}
                className={`px-2 py-1 rounded-md transition-colors ${
                  activeModality.toUpperCase() === m
                    ? "bg-primary text-primary-foreground font-bold shadow"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {m === "STANDARD" ? "RGB" : m === "IR_NIGHT" ? "IR NIGHT" : "THERMAL"}
              </button>
            ))}
          </div>

          {/* Start / Stop Analysis Button */}
          {onToggleRun && (
            <Button
              variant="outline"
              size="sm"
              onClick={onToggleRun}
              className={`h-8 text-xs font-mono flex items-center gap-1.5 transition-all ${
                isRunning
                  ? "border-red-500/40 text-red-400 hover:bg-red-500/20 shadow-red-900/30"
                  : "border-emerald-500/40 text-emerald-400 hover:bg-emerald-500/20 shadow-emerald-900/30"
              }`}
              title={isRunning ? "Stop perception analysis" : "Start live perception analysis"}
            >
              {isRunning ? (
                <>
                  <Square className="w-3 h-3 fill-current" /> STOP ANALYSIS
                </>
              ) : (
                <>
                  <Play className="w-3 h-3 fill-current" /> START ANALYSIS
                </>
              )}
            </Button>
          )}

          {!isDrawing ? (
            <div className="flex items-center gap-2">
              <div className="flex items-center gap-1.5">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => beginDraw("polygon")}
                  className="h-8 text-xs font-mono border-white/10 hover:border-cyan-500/50"
                >
                  <Square className="w-3 h-3 mr-1 text-cyan-400" /> + ZONE
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => beginDraw("tripwire")}
                  className="h-8 text-xs font-mono border-white/10 hover:border-amber-500/50"
                >
                  <Crosshair className="w-3 h-3 mr-1 text-amber-400" /> + TRIPWIRE
                </Button>
              </div>

              {(zones.length > 0 || boundaries.length > 0) && (
                <div className="flex items-center gap-1 bg-black/40 border border-white/10 rounded-lg px-2 py-0.5">
                  <span className="text-[10px] font-mono text-muted-foreground uppercase">TRIGGERS:</span>
                  <select
                    value={selectedTriggerId}
                    onChange={(e) => setSelectedTriggerId(e.target.value)}
                    className="bg-transparent text-[11px] font-mono text-foreground focus:outline-none max-w-[150px] truncate"
                  >
                    <option value="" className="bg-black text-muted-foreground">Select trigger...</option>
                    {zones.map((z) => (
                      <option key={z.zone_id} value={z.zone_id} className="bg-black text-white">
                        [Zone] {z.name}
                      </option>
                    ))}
                    {boundaries.map((b) => (
                      <option key={b.boundary_id} value={b.boundary_id} className="bg-black text-white">
                        [Tripwire] {b.name} ({b.direction || "BIDIR"})
                      </option>
                    ))}
                  </select>
                  {selectedTriggerId && (
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={handleDeleteTrigger}
                      disabled={isDeletingTrigger}
                      className="h-6 px-2 text-[10px] font-mono bg-red-600/80 hover:bg-red-600 flex items-center gap-1"
                    >
                      <Trash2 className="w-3 h-3" /> REMOVE
                    </Button>
                  )}
                </div>
              )}
            </div>
          ) : (
            <div className="flex items-center gap-1.5">
              <input
                type="text"
                placeholder="Zone name..."
                value={zoneName}
                onChange={(e) => setZoneName(e.target.value)}
                className="bg-black/60 border border-white/20 rounded-md px-2 py-1 text-xs font-mono text-foreground focus:outline-none w-36"
              />
              <select
                value={severity}
                onChange={(e) => setSeverity(e.target.value)}
                className="bg-black/60 border border-white/20 rounded-md px-2 py-1 text-xs font-mono text-foreground focus:outline-none"
              >
                <option value="restricted">RESTRICTED</option>
                <option value="critical">CRITICAL</option>
                <option value="normal">NORMAL</option>
              </select>
              {drawMode === "tripwire" && (
                <select
                  value={tripwireDirection}
                  onChange={(e) => setTripwireDirection(e.target.value)}
                  className="bg-black/60 border border-amber-500/40 text-amber-300 rounded-md px-2 py-1 text-xs font-mono focus:outline-none"
                  title="Select tripwire crossing trigger direction"
                >
                  <option value="BIDIRECTIONAL">BOTH (BIDIRECTIONAL)</option>
                  <option value="NORTH">NORTH (UP)</option>
                  <option value="SOUTH">SOUTH (DOWN)</option>
                  <option value="EAST">EAST (RIGHT)</option>
                  <option value="WEST">WEST (LEFT)</option>
                </select>
              )}
              <Button
                size="sm"
                onClick={handleSaveZone}
                disabled={!canSave || isSaving}
                className="h-8 bg-emerald-600 hover:bg-emerald-500 text-xs font-mono"
              >
                <Check className="w-3 h-3 mr-1" /> SAVE
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={cancelDraw}
                className="h-8 text-xs font-mono text-muted-foreground hover:text-foreground"
              >
                <X className="w-3 h-3 mr-1" /> CANCEL
              </Button>
            </div>
          )}
        </div>
      </div>

      {/* Main Video Viewport */}
      <div
        ref={containerRef}
        onClick={handleClick}
        onMouseMove={handleMouseMove}
        className={`flex-1 relative bg-black flex items-center justify-center overflow-hidden ${
          isDrawing ? "cursor-crosshair" : "cursor-default"
        }`}
      >
        <img
          ref={imageRef}
          src={feedUrl}
          alt={cameraName}
          className="max-w-full max-h-full object-contain select-none pointer-events-none"
        />

        {/* Standby Overlay when camera perception is stopped */}
        {!isRunning && (
          <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/85 backdrop-blur-sm">
            <div className="p-8 max-w-md text-center flex flex-col items-center gap-3 border border-white/10 rounded-2xl bg-black/70 shadow-2xl">
              <div className="w-14 h-14 rounded-full bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center">
                <Video className="w-7 h-7 text-cyan-400" />
              </div>
              <h3 className="text-sm font-bold font-mono tracking-widest text-foreground uppercase">
                {cameraId} — STANDBY MODE
              </h3>
              <p className="text-xs text-muted-foreground font-mono leading-relaxed">
                Surveillance perception pipeline is idle. Exactly one camera actively runs real-time neural inference at a time.
              </p>
              {onToggleRun && (
                <Button
                  onClick={onToggleRun}
                  className="mt-3 bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs px-6 py-2.5 rounded-xl shadow-lg shadow-emerald-900/40 flex items-center gap-2 border border-emerald-400/40"
                >
                  <Play className="w-4 h-4 fill-current" /> START ANALYSIS
                </Button>
              )}
            </div>
          </div>
        )}

        {/* Interactive SVG Drawing & Selection Layer */}
        {rect.ready && (
          <svg
            className="absolute z-10 overflow-visible"
            style={{
              left: `${svgLeft}px`,
              top: `${svgTop}px`,
              width: `${rect.displayWidth}px`,
              height: `${rect.displayHeight}px`,
              pointerEvents: isDrawing ? "none" : "auto",
            }}
            viewBox={`0 0 ${rect.frameWidth} ${rect.frameHeight}`}
          >
            {/* Existing Saved Zones (Click to Select / Highlight) */}
            {!isDrawing && zones.map((z) => {
              const isSel = selectedTriggerId === z.zone_id;
              const ptsStr = z.polygon
                .map((p) => `${p[0] * rect.frameWidth},${p[1] * rect.frameHeight}`)
                .join(" ");
              return (
                <g
                  key={z.zone_id}
                  className="cursor-pointer"
                  style={{ pointerEvents: "all" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedTriggerId(z.zone_id);
                  }}
                >
                  <polygon
                    points={ptsStr}
                    fill={isSel ? "rgba(0, 229, 255, 0.35)" : "rgba(0, 229, 255, 0.08)"}
                    stroke={isSel ? "#00E5FF" : "rgba(0, 229, 255, 0.6)"}
                    strokeWidth={isSel ? "5" : "2"}
                    strokeDasharray={isSel ? "8,4" : "none"}
                    style={{ filter: isSel ? "drop-shadow(0 0 10px rgba(0,229,255,0.9))" : "none" }}
                  />
                  {isSel && z.polygon.map((p, pIdx) => (
                    <circle
                      key={pIdx}
                      cx={p[0] * rect.frameWidth}
                      cy={p[1] * rect.frameHeight}
                      r="7"
                      fill="#00E5FF"
                      stroke="#FFFFFF"
                      strokeWidth="2"
                    />
                  ))}
                </g>
              );
            })}

            {/* Existing Saved Tripwires (Click to Select / Highlight) */}
            {!isDrawing && boundaries.map((b) => {
              const isSel = selectedTriggerId === b.boundary_id;
              const x1 = b.pt1[0] * rect.frameWidth;
              const y1 = b.pt1[1] * rect.frameHeight;
              const x2 = b.pt2[0] * rect.frameWidth;
              const y2 = b.pt2[1] * rect.frameHeight;
              return (
                <g
                  key={b.boundary_id}
                  className="cursor-pointer"
                  style={{ pointerEvents: "all" }}
                  onClick={(e) => {
                    e.stopPropagation();
                    setSelectedTriggerId(b.boundary_id);
                  }}
                >
                  <line
                    x1={x1}
                    y1={y1}
                    x2={x2}
                    y2={y2}
                    stroke={isSel ? "#F59E0B" : "rgba(245, 158, 11, 0.7)"}
                    strokeWidth={isSel ? "6" : "3"}
                    strokeDasharray={isSel ? "10,5" : "none"}
                    style={{ filter: isSel ? "drop-shadow(0 0 12px rgba(245,158,11,0.95))" : "none" }}
                  />
                  {isSel && (
                    <>
                      <circle cx={x1} cy={y1} r="8" fill="#F59E0B" stroke="#FFFFFF" strokeWidth="2" />
                      <circle cx={x2} cy={y2} r="8" fill="#F59E0B" stroke="#FFFFFF" strokeWidth="2" />
                    </>
                  )}
                </g>
              );
            })}

            {/* Draw Polygon in Progress */}
            {drawMode === "polygon" && points.length > 0 && (
              <>
                <polygon
                  points={[...points, ...(cursor ? [cursor] : [])].map((p) => `${p[0]},${p[1]}`).join(" ")}
                  fill="rgba(0, 229, 255, 0.2)"
                  stroke="#00e5ff"
                  strokeWidth="3"
                  strokeDasharray="6 3"
                />
                {points.map((p, idx) => (
                  <circle key={idx} cx={p[0]} cy={p[1]} r="6" fill="#00e5ff" stroke="#ffffff" strokeWidth="2" />
                ))}
              </>
            )}

            {/* Draw Tripwire in Progress */}
            {drawMode === "tripwire" && (
              <>
                {points.length === 1 && cursor && (
                  <line
                    x1={points[0][0]}
                    y1={points[0][1]}
                    x2={cursor[0]}
                    y2={cursor[1]}
                    stroke="#ffab00"
                    strokeWidth="4"
                    strokeDasharray="8 4"
                  />
                )}
                {points.length === 2 && (
                  <line
                    x1={points[0][0]}
                    y1={points[0][1]}
                    x2={points[1][0]}
                    y2={points[1][1]}
                    stroke="#ffab00"
                    strokeWidth="4"
                  />
                )}
                {points.map((p, idx) => (
                  <circle key={idx} cx={p[0]} cy={p[1]} r="7" fill="#ffab00" stroke="#ffffff" strokeWidth="2" />
                ))}
              </>
            )}

            {/* Real-time Cursor Indicator for Precise Plotting */}
            {isDrawing && cursor && (
              <g>
                <circle cx={cursor[0]} cy={cursor[1]} r="5" fill="#ffffff" stroke="#00e5ff" strokeWidth="2" />
                <line x1={cursor[0] - 10} y1={cursor[1]} x2={cursor[0] + 10} y2={cursor[1]} stroke="#00e5ff" strokeWidth="1.5" />
                <line x1={cursor[0]} y1={cursor[1] - 10} x2={cursor[0]} y2={cursor[1] + 10} stroke="#00e5ff" strokeWidth="1.5" />
              </g>
            )}
          </svg>
        )}

        {/* Selected Trigger Inspector Card */}
        {selectedTrigger && (
          <div className="absolute bottom-4 left-4 z-30 flex items-center gap-3 bg-black/90 border border-cyan-500/50 rounded-xl px-4 py-2.5 shadow-2xl backdrop-blur-md font-mono text-xs">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-cyan-400 animate-ping" />
              <span className="text-muted-foreground uppercase text-[10px]">SELECTED:</span>
              <span className="font-bold text-foreground">{selectedTrigger.name}</span>
              <Badge variant="outline" className="text-[9px] uppercase px-1.5 py-0 border-cyan-500/40 text-cyan-300">
                {selectedTrigger.type}
              </Badge>
              <Badge
                variant="outline"
                className={`text-[9px] uppercase px-1.5 py-0 ${
                  selectedTrigger.severity.toUpperCase() === "CRITICAL"
                    ? "border-red-500/50 text-red-400"
                    : selectedTrigger.severity.toUpperCase() === "RESTRICTED"
                    ? "border-amber-500/50 text-amber-400"
                    : "border-emerald-500/50 text-emerald-400"
                }`}
              >
                {selectedTrigger.severity}
              </Badge>
              {selectedTrigger.direction && (
                <span className="text-[10px] text-amber-300 bg-amber-500/10 px-1.5 py-0.5 rounded border border-amber-500/30">
                  DIR: {selectedTrigger.direction}
                </span>
              )}
            </div>
            <div className="h-4 w-px bg-white/20" />
            <div className="flex items-center gap-1.5">
              <Button
                variant="destructive"
                size="sm"
                onClick={handleDeleteTrigger}
                disabled={isDeletingTrigger}
                className="h-7 px-3 text-[11px] font-mono bg-red-600 hover:bg-red-500 flex items-center gap-1 shadow-lg shadow-red-950/50"
              >
                <Trash2 className="w-3.5 h-3.5" />
                DELETE {selectedTrigger.type === "ZONE" ? "ZONE" : "TRIPWIRE"}
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setSelectedTriggerId("")}
                className="h-7 w-7 text-muted-foreground hover:text-foreground"
                title="Deselect"
              >
                <X className="w-3.5 h-3.5" />
              </Button>
            </div>
          </div>
        )}

        {/* Video Timeline Seek Replay Banner & Controls */}
        {isSeekMode && (
          <div className="absolute bottom-4 left-4 right-4 bg-black/85 backdrop-blur-xl border border-white/15 rounded-xl p-3 shadow-2xl z-30">
            <div className="flex items-center justify-between gap-4 mb-2">
              <div className="flex items-center gap-2 text-xs font-mono text-cyan-300">
                <Clock className="w-4 h-4 text-cyan-400" />
                <span>INCIDENT REPLAY: {String(selectedAlertTime)}</span>
                <span className="text-muted-foreground text-[11px]">
                  ({seekOffsetSec >= 0 ? `+${seekOffsetSec}` : seekOffsetSec}s)
                </span>
              </div>

              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSeekOffsetSec(-5)}
                  className="h-7 text-[11px] font-mono border-white/10"
                >
                  -5s
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSeekOffsetSec(0)}
                  className="h-7 text-[11px] font-mono border-cyan-500/40 text-cyan-300"
                >
                  EVENT (0s)
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setSeekOffsetSec(5)}
                  className="h-7 text-[11px] font-mono border-white/10"
                >
                  +5s
                </Button>
                <Button
                  size="sm"
                  onClick={onExitSeek}
                  className="h-7 text-[11px] font-mono bg-emerald-600 hover:bg-emerald-500 ml-2"
                >
                  RETURN TO LIVE
                </Button>
              </div>
            </div>

            {/* Seeking Scrubber Range Slider */}
            <input
              type="range"
              min="-10"
              max="10"
              step="0.5"
              value={seekOffsetSec}
              onChange={(e) => setSeekOffsetSec(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-white/20 rounded-lg appearance-none cursor-pointer accent-primary"
            />
          </div>
        )}
      </div>
    </div>
  );
}
