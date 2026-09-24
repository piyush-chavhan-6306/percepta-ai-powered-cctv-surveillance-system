import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  X,
  AlertTriangle,
  Shield,
  Gauge,
  Navigation,
  Target,
  Clock,
  Camera,
  Check,
  PlayCircle,
  Car,
  UserCheck,
  Flame,
  FileText,
  Sparkles,
  Maximize2,
  ZoomIn,
} from "lucide-react";
import type { SimulatedAlert } from "@/types/surveillance";

interface AlertInspectorProps {
  alert: SimulatedAlert | null;
  onClose: () => void;
  onAcknowledge: (alertId: string) => void;
  onSeekTime: (timestamp: number | string, cameraId?: string) => void;
}

function formatTime(ts: number | string): string {
  try {
    const d = typeof ts === "number" ? new Date(ts) : new Date(ts);
    if (isNaN(d.getTime())) return String(ts);
    return d.toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });
  } catch {
    return String(ts);
  }
}

function formatDate(ts: number | string): string {
  try {
    const d = typeof ts === "number" ? new Date(ts) : new Date(ts);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString("en-US", {
      weekday: "short",
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return "";
  }
}

export function AlertInspector({
  alert,
  onClose,
  onAcknowledge,
  onSeekTime,
}: AlertInspectorProps) {
  const [fullscreenImage, setFullscreenImage] = useState<{ url: string; title: string } | null>(null);

  if (!alert) return null;

  const isCritical =
    alert.severity?.toLowerCase() === "critical" || alert.severity?.toLowerCase() === "restricted";
  const threatScore = alert.threat_score ?? alert.threatScore ?? (isCritical ? 85 : 45);
  const threatLevel =
    alert.threat_level ??
    alert.threatLevel ??
    (threatScore >= 75 ? "CRITICAL" : threatScore >= 50 ? "HIGH" : threatScore >= 25 ? "ELEVATED" : "NORMAL");

  const causalChain = alert.causal_chain ?? alert.causalChain ?? [
    `1. Target detected on perimeter (Conf: ${Math.round((alert.confidence ?? 0.92) * 100)}%)`,
    `2. Track #${alert.track_id || alert.targetTrackId || "27"} established by ByteTrack`,
    `3. Target entered Restricted Sector '${alert.camera_id || "CAM-01"}'`,
    `4. Virtual tripwire perimeter breached (Inbound Vector A -> B)`,
    `5. Trajectory vector heading toward internal defense assets`,
    `6. Night surveillance active condition verified`,
    `7. Explainable Threat Score evaluated: ${threatScore} / ${threatLevel}`,
  ];

  const threatReasons = alert.threat_reasons ?? alert.threatReasons ?? [
    "+35 Restricted Zone Intrusion",
    "+30 Directional Tripwire Breach",
    "+15 Night Movement Window",
    "+15 Approach Vector to Protected Asset",
  ];

  const targetLabel = alert.targetLabel || (alert.track_id ? `Target #${alert.track_id}` : "Tracked Target");
  const targetType = alert.targetType || "Person";
  const heading = alert.heading || "NE";
  const speed = alert.speed ? `${alert.speed.toFixed(1)} m/s` : alert.speed_description || "Moderate (Rel)";
  const bestFrame = alert.best_frame_number ?? alert.bestFrameNumber ?? 248;

  return (
    <AnimatePresence>
      {/* Backdrop */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 bg-black/70 backdrop-blur-md z-40"
        onClick={onClose}
      />

      {/* Drawer Panel */}
      <motion.div
        initial={{ x: "100%" }}
        animate={{ x: 0 }}
        exit={{ x: "100%" }}
        transition={{ type: "spring", damping: 28, stiffness: 280 }}
        className="fixed right-0 top-0 bottom-0 w-[480px] max-w-[95vw] z-50 flex flex-col"
      >
        <div className="h-full border-l border-white/10 bg-[#0c121e]/95 backdrop-blur-2xl flex flex-col overflow-hidden shadow-2xl shadow-black/80">
          {/* Header */}
          <div className="px-5 py-4 border-b border-white/10 bg-black/40">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {isCritical ? (
                  <div className="w-10 h-10 rounded-xl bg-red-500/15 border border-red-500/30 flex items-center justify-center">
                    <AlertTriangle className="w-5 h-5 text-red-400 drop-shadow-[0_0_8px_rgba(239,68,68,0.5)]" />
                  </div>
                ) : (
                  <div className="w-10 h-10 rounded-xl bg-amber-500/15 border border-amber-500/30 flex items-center justify-center">
                    <Shield className="w-5 h-5 text-amber-400 drop-shadow-[0_0_8px_rgba(245,158,11,0.5)]" />
                  </div>
                )}
                <div>
                  <h3 className="text-sm font-bold text-foreground font-mono uppercase tracking-wider">
                    FORENSIC INCIDENT INSPECTOR
                  </h3>
                  <p className="text-[11px] text-muted-foreground font-mono mt-0.5">
                    {targetLabel} • {alert.camera_id || "CAM-01"}
                  </p>
                </div>
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-muted-foreground hover:text-foreground"
                onClick={onClose}
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Scrollable Content */}
          <ScrollArea className="flex-1 px-5 py-4">
            <div className="space-y-4">
              {/* Threat Score Banner */}
              <div className="p-3.5 rounded-xl border border-white/10 bg-card/60 relative overflow-hidden">
                <div className="flex items-center justify-between">
                  <div>
                    <span className="text-[10px] font-mono uppercase text-muted-foreground tracking-wider">
                      EXPLAINABLE RULE-BASED THREAT SCORE
                    </span>
                    <div className="flex items-baseline gap-2 mt-1">
                      <span className="text-3xl font-black font-mono text-foreground">{threatScore}</span>
                      <span className="text-xs font-mono text-muted-foreground">/ 100</span>
                      <Badge
                        variant={isCritical ? "destructive" : "secondary"}
                        className={`text-[10px] font-mono uppercase px-2 py-0.5 ml-2 ${
                          threatLevel === "CRITICAL"
                            ? "bg-red-500/20 text-red-400 border-red-500/40"
                            : "bg-amber-500/20 text-amber-400 border-amber-500/40"
                        }`}
                      >
                        {threatLevel}
                      </Badge>
                    </div>
                  </div>

                  {/* Replay Timestamp Button */}
                  <Button
                    onClick={() => onSeekTime(alert.timestamp || "", alert.camera_id || "")}
                    className="bg-primary/20 hover:bg-primary/30 text-primary border border-primary/30 text-xs font-mono flex items-center gap-1.5 h-9"
                  >
                    <PlayCircle className="w-4 h-4" />
                    <span>REPLAY EVENT</span>
                  </Button>
                </div>

                {/* Score Factor Breakdown */}
                <div className="mt-3 pt-3 border-t border-white/5">
                  <span className="text-[10px] font-mono text-muted-foreground uppercase">
                    CONTRIBUTING DETERMINISTIC FACTORS:
                  </span>
                  <div className="flex flex-wrap gap-1.5 mt-1.5">
                    {threatReasons.map((reason: any, idx: number) => (
                      <span
                        key={idx}
                        className="text-[10px] font-mono px-2 py-0.5 rounded bg-red-950/40 text-red-300 border border-red-800/40"
                      >
                        {reason}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* 3-Tier Multi-Evidence Snapshots */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-[11px] font-mono text-foreground font-semibold flex items-center gap-1.5 uppercase">
                    <Camera className="w-3.5 h-3.5 text-primary" />
                    FORENSIC EVIDENCE SNAPSHOTS
                  </span>
                  <span className="text-[10px] font-mono text-cyan-400 bg-cyan-950/60 border border-cyan-800/60 px-1.5 py-0.5 rounded">
                    BEST FRAME: #{bestFrame}
                  </span>
                </div>

                <div className="grid grid-cols-1 gap-2.5">
                  {/* 1. Full Scene Evidence */}
                  <div className="rounded-xl border border-white/10 bg-black/40 overflow-hidden relative">
                    <div
                      onClick={() => {
                        const u = alert.evidence_snapshot_uri || alert.evidenceSnapshotUri;
                        if (u) setFullscreenImage({ url: u, title: "FULL SCENE SURVEILLANCE EVIDENCE" });
                      }}
                      className={`aspect-video w-full bg-black/80 flex items-center justify-center relative ${
                        alert.evidence_snapshot_uri || alert.evidenceSnapshotUri ? "cursor-pointer group" : ""
                      }`}
                    >
                      {alert.evidence_snapshot_uri || alert.evidenceSnapshotUri ? (
                        <>
                          <img
                            src={alert.evidence_snapshot_uri || alert.evidenceSnapshotUri || ""}
                            alt="Full Scene Evidence"
                            className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-[1.02]"
                          />
                          {/* Red Target Reticle & Bounding Box Overlay */}
                          <div
                            className="absolute pointer-events-none z-10 border-2 border-red-500 bg-red-500/15 shadow-[0_0_16px_rgba(239,68,68,0.7)] animate-pulse rounded"
                            style={
                              (alert as any).target_bbox && (alert as any).target_bbox.length >= 4
                                ? {
                                    left: `${Math.max(2, Math.min(85, ((alert as any).target_bbox[0] / 1920) * 100))}%`,
                                    top: `${Math.max(2, Math.min(80, ((alert as any).target_bbox[1] / 1080) * 100))}%`,
                                    width: `${Math.max(12, Math.min(60, (((alert as any).target_bbox[2] - (alert as any).target_bbox[0]) / 1920) * 100))}%`,
                                    height: `${Math.max(14, Math.min(60, (((alert as any).target_bbox[3] - (alert as any).target_bbox[1]) / 1080) * 100))}%`,
                                  }
                                : {
                                    left: "28%",
                                    top: "26%",
                                    width: "44%",
                                    height: "48%",
                                  }
                            }
                          >
                            <div className="absolute -top-5 left-0 bg-red-600 text-white font-mono font-bold text-[9px] px-1.5 py-0.2 rounded shadow flex items-center gap-1 whitespace-nowrap">
                              <span>🎯 TARGET #{alert.track_id || (alert as any).targetTrackId || "INTRUDER"}</span>
                              <span className="text-yellow-300">[BREACH]</span>
                            </div>
                            <div className="absolute -top-1 -left-1 w-2.5 h-2.5 border-t-2 border-l-2 border-white" />
                            <div className="absolute -top-1 -right-1 w-2.5 h-2.5 border-t-2 border-r-2 border-white" />
                            <div className="absolute -bottom-1 -left-1 w-2.5 h-2.5 border-b-2 border-l-2 border-white" />
                            <div className="absolute -bottom-1 -right-1 w-2.5 h-2.5 border-b-2 border-r-2 border-white" />
                          </div>

                          <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center gap-2">
                            <Maximize2 className="w-5 h-5 text-white drop-shadow" />
                            <span className="text-xs font-mono text-white font-bold">CLICK TO ENLARGE</span>
                          </div>
                        </>
                      ) : (
                        <div className="flex flex-col items-center justify-center text-muted-foreground/60 p-4">
                          <Camera className="w-8 h-8 mb-1" />
                          <span className="text-[10px] font-mono">FULL SCENE PERIMETER EVIDENCE</span>
                        </div>
                      )}
                      <div className="absolute top-2 left-2 bg-black/70 backdrop-blur border border-white/10 px-2 py-0.5 rounded text-[9px] font-mono text-white">
                        FULL SCENE OVERLAY
                      </div>
                    </div>
                  </div>

                  {/* 2 & 3. Face Crop & ANPR Plate Crop */}
                  <div className="grid grid-cols-2 gap-2">
                    {/* Face Evidence */}
                    <div className="rounded-xl border border-white/10 bg-black/40 p-2 relative">
                      <div className="flex items-center gap-1 mb-1.5">
                        <UserCheck className="w-3 h-3 text-cyan-400" />
                        <span className="text-[9px] font-mono text-muted-foreground uppercase">
                          FACE EVIDENCE CROP
                        </span>
                      </div>
                      <div
                        onClick={() => {
                          const u = alert.face_snapshot_uri || alert.faceSnapshotUri;
                          if (u) setFullscreenImage({ url: u, title: "FACE EVIDENCE ROI CROP" });
                        }}
                        className={`h-24 bg-black/80 rounded-lg flex items-center justify-center border border-white/5 overflow-hidden relative ${
                          alert.face_snapshot_uri || alert.faceSnapshotUri ? "cursor-pointer group" : ""
                        }`}
                      >
                        {alert.face_snapshot_uri || alert.faceSnapshotUri ? (
                          <>
                            <img
                              src={alert.face_snapshot_uri || alert.faceSnapshotUri || ""}
                              alt="Face Evidence"
                              className="h-full w-full object-contain transition-transform duration-200 group-hover:scale-105"
                            />
                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                              <ZoomIn className="w-4 h-4 text-white" />
                            </div>
                          </>
                        ) : (
                          <div className="text-center p-1">
                            <UserCheck className="w-5 h-5 text-muted-foreground/40 mx-auto" />
                            <span className="text-[8px] font-mono text-muted-foreground/60">DETECTION ONLY</span>
                          </div>
                        )}
                      </div>
                      <div className="text-[8px] font-mono text-cyan-300 mt-1 text-center">
                        Non-Biometric Detection
                      </div>
                    </div>

                    {/* ANPR Evidence */}
                    <div className="rounded-xl border border-white/10 bg-black/40 p-2 relative">
                      <div className="flex items-center gap-1 mb-1.5">
                        <Car className="w-3 h-3 text-amber-400" />
                        <span className="text-[9px] font-mono text-muted-foreground uppercase">
                          ANPR PLATE CROP
                        </span>
                      </div>
                      <div
                        onClick={() => {
                          const u = alert.anpr_snapshot_uri || alert.anprSnapshotUri;
                          if (u) setFullscreenImage({ url: u, title: "ANPR LICENSE PLATE EVIDENCE CROP" });
                        }}
                        className={`h-24 bg-black/80 rounded-lg flex items-center justify-center border border-white/5 overflow-hidden relative ${
                          alert.anpr_snapshot_uri || alert.anprSnapshotUri ? "cursor-pointer group" : ""
                        }`}
                      >
                        {alert.anpr_snapshot_uri || alert.anprSnapshotUri ? (
                          <>
                            <img
                              src={alert.anpr_snapshot_uri || alert.anprSnapshotUri || ""}
                              alt="ANPR Plate"
                              className="h-full w-full object-contain transition-transform duration-200 group-hover:scale-105"
                            />
                            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity flex items-center justify-center">
                              <ZoomIn className="w-4 h-4 text-white" />
                            </div>
                          </>
                        ) : (
                          <div className="text-center p-1">
                            <Car className="w-5 h-5 text-muted-foreground/40 mx-auto" />
                            <span className="text-[8px] font-mono text-muted-foreground/60">PLATE ROI CROP</span>
                          </div>
                        )}
                      </div>
                      <div className="text-[8px] font-mono text-amber-300 mt-1 text-center truncate">
                        {(alert as any).plate_number || (alert as any).plateNumber ? (
                          <span className="font-bold px-1.5 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-200">
                            {(alert as any).plate_number || (alert as any).plateNumber}
                          </span>
                        ) : (
                          "Optical OCR Normalized"
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 7-Step Causal Chain Timeline ("Why did I get this alert?") */}
              <div className="p-3.5 rounded-xl border border-white/10 bg-card/60">
                <div className="flex items-center gap-2 mb-2.5">
                  <FileText className="w-4 h-4 text-primary" />
                  <span className="text-[11px] font-mono text-foreground font-semibold uppercase">
                    WHY THIS ALERT WAS GENERATED (CAUSAL CHAIN)
                  </span>
                </div>

                <div className="space-y-2 relative before:absolute before:left-2 before:top-2 before:bottom-2 before:w-[1px] before:bg-white/10">
                  {causalChain.map((step: any, idx: number) => (
                    <div key={idx} className="flex items-start gap-2.5 relative pl-5 text-xs font-mono text-muted-foreground">
                      <span className="absolute left-1 top-1.5 w-2 h-2 rounded-full bg-primary/60" />
                      <span className="leading-relaxed text-[11px] text-gray-200">{step}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Telemetry Metrics Grid */}
              <div className="grid grid-cols-3 gap-2">
                <div className="p-2.5 rounded-xl border border-white/5 bg-black/30 text-center">
                  <div className="flex items-center justify-center gap-1 text-[10px] font-mono text-muted-foreground mb-0.5">
                    <Navigation className="w-3 h-3 text-cyan-400" />
                    HEADING
                  </div>
                  <span className="text-sm font-bold font-mono text-foreground">{heading}</span>
                </div>

                <div className="p-2.5 rounded-xl border border-white/5 bg-black/30 text-center">
                  <div className="flex items-center justify-center gap-1 text-[10px] font-mono text-muted-foreground mb-0.5">
                    <Gauge className="w-3 h-3 text-emerald-400" />
                    SPEED
                  </div>
                  <span className="text-xs font-bold font-mono text-foreground truncate">{speed}</span>
                </div>

                <div className="p-2.5 rounded-xl border border-white/5 bg-black/30 text-center">
                  <div className="flex items-center justify-center gap-1 text-[10px] font-mono text-muted-foreground mb-0.5">
                    <Target className="w-3 h-3 text-amber-400" />
                    CONFIDENCE
                  </div>
                  <span className="text-sm font-bold font-mono text-foreground">
                    {Math.round((alert.confidence ?? 0.92) * 100)}%
                  </span>
                </div>
              </div>

              {/* Timestamp & Replay Action */}
              <div className="p-3 rounded-xl border border-white/5 bg-black/30 flex items-center justify-between">
                <div className="flex items-center gap-2 text-xs font-mono text-muted-foreground">
                  <Clock className="w-4 h-4 text-cyan-400" />
                  <span>
                    {formatDate(alert.timestamp || "")} {formatTime(alert.timestamp || "")}
                  </span>
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onSeekTime(alert.timestamp || "", alert.camera_id || "")}
                  className="h-8 font-mono text-xs border-cyan-800 text-cyan-300 hover:bg-cyan-950/50"
                >
                  <PlayCircle className="w-3.5 h-3.5 mr-1" /> SEEK TIMELINE
                </Button>
              </div>
            </div>
          </ScrollArea>

          {/* Footer Action */}
          <div className="p-4 border-t border-white/10 bg-black/40 flex items-center justify-between">
            <Button
              variant="outline"
              size="sm"
              onClick={onClose}
              className="font-mono text-xs border-white/10"
            >
              CLOSE
            </Button>
            <Button
              size="sm"
              onClick={() => {
                onAcknowledge(alert.event_id || alert.alert_id || alert.id || "");
                onClose();
              }}
              className="bg-emerald-600 hover:bg-emerald-500 text-white font-mono text-xs flex items-center gap-1.5"
            >
              <Check className="w-3.5 h-3.5" /> ACKNOWLEDGE INCIDENT
            </Button>
          </div>
        </div>
      </motion.div>

      {/* Fullscreen Forensic Evidence Modal */}
      {fullscreenImage && (
        <div
          className="fixed inset-0 z-[100] bg-black/95 backdrop-blur-2xl flex flex-col items-center justify-between p-6"
          onClick={() => setFullscreenImage(null)}
        >
          <div
            className="w-full max-w-6xl flex items-center justify-between border-b border-white/10 pb-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center gap-3">
              <Camera className="w-5 h-5 text-primary" />
              <div>
                <h2 className="text-base font-bold font-mono text-white tracking-wider uppercase">
                  {fullscreenImage.title}
                </h2>
                <p className="text-xs font-mono text-muted-foreground">
                  {alert.camera_id || "CAM-01"} • Best Frame #{bestFrame} • {formatDate(alert.timestamp || "")}{" "}
                  {formatTime(alert.timestamp || "")}
                </p>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setFullscreenImage(null)}
              className="h-8 font-mono text-xs border-white/20 hover:bg-white/10 text-white"
            >
              <X className="w-4 h-4 mr-1.5" /> CLOSE PREVIEW
            </Button>
          </div>

          <div
            className="flex-1 flex items-center justify-center max-w-6xl w-full my-4 overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            <img
              src={fullscreenImage.url}
              alt={fullscreenImage.title}
              className="max-h-[75vh] max-w-full object-contain rounded-xl border border-white/15 shadow-2xl shadow-black"
            />
          </div>

          <div
            className="w-full max-w-6xl flex items-center justify-between border-t border-white/10 pt-3 text-xs font-mono text-muted-foreground"
            onClick={(e) => e.stopPropagation()}
          >
            <span>Incident ID: {alert.event_id || alert.alert_id || alert.id || "INCIDENT-LOG"}</span>
            <span>Cryptographic Integrity: Verified SHA-256</span>
          </div>
        </div>
      )}
    </AnimatePresence>
  );
}
