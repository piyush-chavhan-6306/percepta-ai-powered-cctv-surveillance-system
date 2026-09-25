import React, { useState, useEffect, useRef } from "react";
import { api } from "../api/client";
import type { CameraRecord } from "../types/surveillance";
import {
  Camera,
  Moon,
  Flame,
  Video,
  Radio,
  Upload,
  X,
  Check,
  AlertCircle,
  Loader2,
  FileVideo,
  Server,
  Wifi,
  WifiOff,
  RefreshCw,
} from "lucide-react";

interface AddCameraModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCameraAdded: (camera: CameraRecord, previewUrl?: string) => void;
}

export interface IngestionErrorInfo {
  backendUrl: string;
  isReachable: boolean;
  endpoint: string;
  status: string;
  reason: string;
  remediation?: string;
}

const DEFAULT_BUNDLED_CLIPS: Array<{ name: string; path: string; size_mb: number }> = [
  { name: "Sector Alpha — Border Intruder Detection (cam01_person_border.mp4)", path: "/videos/cam01_person_border.mp4", size_mb: 5.4 },
  { name: "Sector Bravo — Multi-Target Perimeter Tracking (cam02_tracking.mp4)", path: "/videos/cam02_tracking.mp4", size_mb: 1.9 },
  { name: "Sector Charlie — Vehicle Checkpoint ANPR (cam03_vehicle.mp4)", path: "/videos/cam03_vehicle.mp4", size_mb: 5.1 },
  { name: "Sector Delta — Night Vision Thermal IR (cam04_night_ir.mp4)", path: "/videos/cam04_night_ir.mp4", size_mb: 2.8 },
  { name: "Sector Echo — Wide-Area Drone Surveillance (virat_cctv.mp4)", path: "/videos/virat_cctv.mp4", size_mb: 5.4 },
];

export const AddCameraModal: React.FC<AddCameraModalProps> = ({
  isOpen,
  onClose,
  onCameraAdded,
}) => {
  // Source selection
  const [sourceType, setSourceType] = useState<"video_file" | "rtsp" | "webcam">("video_file");

  // Sensor Modality
  const [modality, setModality] = useState<"STANDARD" | "IR" | "THERMAL">("STANDARD");

  // Inputs
  const [cameraId, setCameraId] = useState("");
  const [cameraName, setCameraName] = useState("");
  const [locationLabel, setLocationLabel] = useState("Sector 9 North Perimeter");
  const [fps, setFps] = useState<number>(30);
  const [deviceIndex, setDeviceIndex] = useState<number>(0);
  const [rtspUrl, setRtspUrl] = useState("");

  // Upload & Bundled Clips
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [selectedClip, setSelectedClip] = useState(DEFAULT_BUNDLED_CLIPS[0].path);
  const [availableClips, setAvailableClips] = useState<Array<{ name: string; path: string; size_mb: number }>>(DEFAULT_BUNDLED_CLIPS);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Submission & Diagnostic State
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorDetails, setErrorDetails] = useState<IngestionErrorInfo | null>(null);
  const [showBackendConfig, setShowBackendConfig] = useState(false);
  const [backendUrlInput, setBackendUrlInput] = useState(api.getBaseUrl() || "");
  const [isTestingBackend, setIsTestingBackend] = useState(false);
  const [backendHealthStatus, setBackendHealthStatus] = useState<{ ok: boolean; message: string } | null>(null);

  useEffect(() => {
    if (isOpen) {
      setErrorDetails(null);
      const randomNum = Math.floor(10 + Math.random() * 90);
      const randomId = `CAM-${randomNum}`;
      setCameraId(randomId);
      setCameraName(`Sector ${randomNum} North Fence, Checkpoint Alpha`);
      setUploadFile(null);
      setIsDragging(false);
      setBackendUrlInput(api.getBaseUrl() || "");
      setAvailableClips(DEFAULT_BUNDLED_CLIPS);
      setSelectedClip(DEFAULT_BUNDLED_CLIPS[0].path);

      // Probe backend health passively to inform the operator immediately
      api.probeHealth().then((res) => {
        if (res.ok) {
          setBackendHealthStatus({ ok: true, message: `Connected (${res.service || "PERCEPTA API"})` });
        } else {
          setBackendHealthStatus({ ok: false, message: res.error || "Backend Offline / Local Fast Mode" });
        }
      });

      api.getAvailableSources()
        .then((res) => {
          const all = [...(res.bundled_clips || []), ...(res.uploaded_clips || [])];
          if (all.length > 0) {
            setAvailableClips(all);
            setSelectedClip(all[0].path);
          }
        })
        .catch(() => {});
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      const file = e.dataTransfer.files[0];
      setUploadFile(file);
      setSelectedClip("");
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setUploadFile(e.target.files[0]);
      setSelectedClip("");
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setErrorDetails(null);

    try {
      if (sourceType === "video_file") {
        if (uploadFile) {
          const previewUrl = URL.createObjectURL(uploadFile);
          const localCam: CameraRecord = {
            camera_id: cameraId || `CAM-${Math.floor(10 + Math.random() * 90)}`,
            name: cameraName || uploadFile.name.replace(/\.[^/.]+$/, ""),
            source_type: "video_file",
            source_url: previewUrl,
            location_label: locationLabel || "Custom Upload Feed",
            status: "online",
            resolution: "1920x1080",
            native_fps: fps,
            fps: fps,
            frames_processed: 0,
            dropped_frames: 0,
            last_seen: new Date().toISOString(),
            is_running: true,
            preview_url: previewUrl,
            modality: modality,
          };
          onCameraAdded(localCam, previewUrl);
          onClose();

          // Asynchronous backend upload if alive
          if (backendHealthStatus?.ok) {
            const formData = new FormData();
            formData.append("file", uploadFile);
            formData.append("camera_id", localCam.camera_id);
            formData.append("name", localCam.name);
            formData.append("location_label", localCam.location_label);
            formData.append("loop", "true");
            api.uploadCameraVideo(formData).catch(() => {});
          }
          return;
        }

        const clipToUse = selectedClip || DEFAULT_BUNDLED_CLIPS[0].path;
        const chosenMeta = availableClips.find((c) => c.path === clipToUse) || DEFAULT_BUNDLED_CLIPS[0];
        const localCam: CameraRecord = {
          camera_id: cameraId || `CAM-${Math.floor(10 + Math.random() * 90)}`,
          name: cameraName || chosenMeta.name,
          source_type: "bundled_video",
          source_url: clipToUse,
          location_label: locationLabel || "Perimeter Sector",
          status: "online",
          resolution: "1920x1080",
          native_fps: fps,
          fps: fps,
          frames_processed: 0,
          dropped_frames: 0,
          last_seen: new Date().toISOString(),
          is_running: true,
          preview_url: clipToUse,
          modality: modality,
        };
        onCameraAdded(localCam, clipToUse);
        onClose();

        if (backendHealthStatus?.ok) {
          api.registerCamera({
            camera_id: localCam.camera_id,
            name: localCam.name,
            source_type: "video_file",
            source_url: clipToUse,
            location_label: localCam.location_label,
            fps: fps,
            loop: true,
            autostart: true,
            modality: modality,
          }).catch(() => {});
        }
        return;
      } else if (sourceType === "webcam") {
        const localCam: CameraRecord = {
          camera_id: cameraId || `CAM-${Math.floor(10 + Math.random() * 90)}`,
          name: cameraName || `Webcam ${deviceIndex}`,
          source_type: "webcam",
          source_url: deviceIndex.toString(),
          location_label: locationLabel || "Local Optical Sensor",
          status: "online",
          resolution: "1280x720",
          native_fps: fps,
          fps: fps,
          frames_processed: 0,
          dropped_frames: 0,
          last_seen: new Date().toISOString(),
          is_running: true,
          modality: modality,
        };
        onCameraAdded(localCam);
        onClose();

        if (backendHealthStatus?.ok) {
          api.registerCamera({
            camera_id: localCam.camera_id,
            name: localCam.name,
            source_type: "webcam",
            source_url: deviceIndex.toString(),
            device_index: deviceIndex,
            location_label: localCam.location_label,
            fps: fps,
            autostart: true,
            modality: modality,
          }).catch(() => {});
        }
        return;
      } else if (sourceType === "rtsp") {
        if (!rtspUrl.trim()) {
          throw new Error("RTSP stream URL is required (e.g. rtsp://192.168.1.50:554/live)");
        }
        const localCam: CameraRecord = {
          camera_id: cameraId || `CAM-${Math.floor(10 + Math.random() * 90)}`,
          name: cameraName || "RTSP Stream",
          source_type: "rtsp",
          source_url: rtspUrl.trim(),
          location_label: locationLabel || "Remote IP Stream",
          status: "online",
          resolution: "1920x1080",
          native_fps: fps,
          fps: fps,
          frames_processed: 0,
          dropped_frames: 0,
          last_seen: new Date().toISOString(),
          is_running: true,
          modality: modality,
        };
        onCameraAdded(localCam);
        onClose();

        if (backendHealthStatus?.ok) {
          api.registerCamera({
            camera_id: localCam.camera_id,
            name: localCam.name,
            source_type: "rtsp",
            source_url: rtspUrl.trim(),
            location_label: localCam.location_label,
            fps: fps,
            autostart: true,
            modality: modality,
          }).catch(() => {});
        }
        return;
      }
    } catch (err: any) {
      const endpoint = err.endpoint || (sourceType === "video_file" && uploadFile ? "/api/cameras/upload" : "/api/cameras/register");
      const currentBase = api.getBaseUrl();
      const isHttps = typeof window !== "undefined" && window.location.protocol === "https:";
      const isCallingHttp = currentBase.startsWith("http://");

      const probe = await api.probeHealth();

      let reason = err.message || "Unknown ingestion error occurred";
      let statusStr = err.status ? `HTTP ${err.status}` : (probe.error || "Connection Refused / Network Error");
      let remediation = "";

      if (err.isNetworkError || err.message === "Failed to fetch") {
        if (isHttps && isCallingHttp) {
          reason = "Browser Mixed Content Policy: The browser strictly blocked calling an insecure HTTP backend from an HTTPS deployed origin.";
          remediation = "Configure a secure HTTPS backend URL (e.g. via Cloudflare Tunnel, ngrok, or cloud deployment) or access the C2 locally over HTTP.";
        } else if (!probe.ok) {
          reason = "Inference backend is offline or unreachable from the current browser network environment.";
          remediation = "Ensure the FastAPI backend process is running (`uvicorn backend.main:app`) and configure its public HTTPS address below.";
        } else {
          reason = `Network failure communicating with ${endpoint}: ${err.message}`;
          remediation = "Verify CORS permissions on the backend and inspect browser DevTools console.";
        }
      } else if (err.status === 405) {
        reason = "HTTP 405 Method Not Allowed: The request was routed to a static hosting layer (Vercel CDN) instead of an active FastAPI server.";
        remediation = "Configure VITE_API_URL or enter a dedicated backend URL below to route camera creation to your inference server.";
      } else if (err.status === 404) {
        reason = `HTTP 404 Not Found: Camera registration route was not found at ${currentBase || (typeof window !== "undefined" ? window.location.origin : "Local")}.`;
      } else if (err.status === 400 || err.status === 422) {
        reason = `Validation / Ingestion Error: ${err.message}`;
      }

      setErrorDetails({
        backendUrl: currentBase || (typeof window !== "undefined" ? window.location.origin : "Default Local"),
        isReachable: probe.ok,
        endpoint,
        status: statusStr,
        reason,
        remediation,
      });
      setShowBackendConfig(true);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 sm:p-6 select-none overflow-y-auto">
      {/* ── Main Modal Container (Spacious ~640px Max Width) ── */}
      <div
        className="w-full max-w-2xl bg-[#090d13] border border-[#1e2a38] rounded-2xl shadow-[0_20px_60px_rgba(0,0,0,0.85)] overflow-hidden flex flex-col font-sans relative my-auto"
        data-purpose="register-surveillance-feed-modal"
      >
        {/* Top Decorative Cyan Accent Line */}
        <div className="h-[2px] w-full bg-gradient-to-r from-transparent via-[#33f0b4] to-transparent opacity-80" />

        {/* ── 1. Modal Header ── */}
        <div className="px-6 py-5 border-b border-[#1b2530] bg-[#0a0f16] flex items-center justify-between shrink-0">
          <div className="flex items-center gap-3.5">
            <div className="w-10 h-10 rounded-xl bg-[#33f0b4]/10 border border-[#33f0b4]/35 flex items-center justify-center text-[#33f0b4] shadow-[0_0_12px_rgba(51,240,180,0.2)] shrink-0">
              <Camera size={20} strokeWidth={2} />
            </div>
            <div>
              <div className="flex items-center gap-2.5">
                <h2 className="font-['Chakra_Petch',sans-serif] font-bold text-base tracking-wider text-white uppercase leading-tight">
                  REGISTER SURVEILLANCE FEED
                </h2>
                {backendHealthStatus && (
                  <span
                    className={`text-[9px] font-mono px-2 py-0.5 rounded-full border font-bold flex items-center gap-1 ${
                      backendHealthStatus.ok
                        ? "bg-[#33f0b4]/15 border-[#33f0b4]/40 text-[#33f0b4]"
                        : "bg-[#ff4757]/15 border-[#ff4757]/40 text-[#ff6b81]"
                    }`}
                  >
                    {backendHealthStatus.ok ? <Wifi size={9} /> : <WifiOff size={9} />}
                    <span>{backendHealthStatus.ok ? "BACKEND ONLINE" : "BACKEND OFFLINE"}</span>
                  </span>
                )}
              </div>
              <p className="text-[11px] font-mono text-[#8b9bb0] tracking-wide mt-0.5">
                Connect an IP/RTSP camera, optical webcam, or upload any video file for AI perception.
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={onClose}
            className="w-8 h-8 rounded-lg border border-[#1b2530] bg-[#0c1015] hover:bg-white/10 text-[#869099] hover:text-white flex items-center justify-center transition-colors cursor-pointer"
            title="Close Dialog"
          >
            <X size={16} />
          </button>
        </div>

        {/* ── 2. Modal Body Form ── */}
        <form onSubmit={handleSubmit} className="p-6 space-y-5 text-xs font-sans">
          {/* Phase 16: Structured Ingestion Error Diagnostic Card */}
          {errorDetails && (
            <div className="p-4 bg-[#ff4757]/10 border border-[#ff4757]/40 rounded-xl font-mono text-xs text-[#ff6b81] space-y-2.5 shadow-lg">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 font-bold text-[#ff4757] uppercase tracking-wider">
                  <AlertCircle size={16} />
                  <span>INGESTION FAILED</span>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded font-bold uppercase bg-[#ff4757]/20 border border-[#ff4757]/40 text-[#ff6b81]">
                  {errorDetails.status}
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1 text-[11px] border-t border-[#ff4757]/20">
                <div>
                  <span className="text-[#8b9bb0] block text-[9.5px] uppercase font-bold">BACKEND:</span>
                  <span className="text-white font-bold break-all">
                    {errorDetails.backendUrl || "Default Local"}{" "}
                    <span className={errorDetails.isReachable ? "text-[#33f0b4]" : "text-[#ff6b81]"}>
                      [{errorDetails.isReachable ? "REACHABLE" : "UNREACHABLE"}]
                    </span>
                  </span>
                </div>

                <div>
                  <span className="text-[#8b9bb0] block text-[9.5px] uppercase font-bold">ENDPOINT:</span>
                  <span className="text-white font-mono">{errorDetails.endpoint}</span>
                </div>

                <div>
                  <span className="text-[#8b9bb0] block text-[9.5px] uppercase font-bold">STATUS:</span>
                  <span className="text-[#ff6b81] font-bold">{errorDetails.status}</span>
                </div>

                <div className="sm:col-span-2">
                  <span className="text-[#8b9bb0] block text-[9.5px] uppercase font-bold">REASON:</span>
                  <span className="text-[#e2e8f0]">{errorDetails.reason}</span>
                </div>

                {errorDetails.remediation && (
                  <div className="sm:col-span-2 pt-1.5 text-[#33f0b4] text-[10px] border-t border-[#ff4757]/20 flex flex-col gap-0.5">
                    <span className="font-bold uppercase tracking-wider text-[#33f0b4]">TACTICAL REMEDIATION:</span>
                    <span className="text-[#a7f3d0]">{errorDetails.remediation}</span>
                  </div>
                )}
              </div>

              <div className="pt-2 border-t border-[#ff4757]/20 flex items-center justify-between">
                <button
                  type="button"
                  onClick={() => setShowBackendConfig((prev) => !prev)}
                  className="text-[10.5px] font-mono text-[#33f0b4] hover:underline flex items-center gap-1 cursor-pointer font-bold"
                >
                  <Server size={12} />
                  <span>{showBackendConfig ? "▲ HIDE BACKEND CONNECTION CONFIG" : "▼ CONFIGURE INFERENCE BACKEND URL"}</span>
                </button>
              </div>
            </div>
          )}

          {/* Interactive Backend Connection Settings Drawer */}
          {showBackendConfig && (
            <div className="p-3.5 bg-[#0a0f18] border border-[#22364a] rounded-xl font-mono text-xs space-y-2.5 shadow-inner">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 text-[#33f0b4] font-bold text-[10.5px] uppercase tracking-wider">
                  <Server size={13} />
                  <span>INFERENCE BACKEND CONNECTION URL</span>
                </div>
                {backendHealthStatus && (
                  <span className={`text-[9.5px] px-2 py-0.5 rounded font-bold uppercase ${
                    backendHealthStatus.ok ? "bg-[#33f0b4]/15 text-[#33f0b4] border border-[#33f0b4]/30" : "bg-[#ff4757]/15 text-[#ff6b81] border border-[#ff4757]/30"
                  }`}>
                    {backendHealthStatus.message}
                  </span>
                )}
              </div>

              <div className="flex items-center gap-2">
                <input
                  type="text"
                  value={backendUrlInput}
                  onChange={(e) => setBackendUrlInput(e.target.value)}
                  placeholder="e.g. https://my-percepta.ngrok-free.app or http://127.0.0.1:8000"
                  className="flex-1 h-9 bg-[#05070a] border border-[#1e2a38] text-white px-3 rounded-lg text-xs font-mono focus:outline-none focus:border-[#33f0b4]"
                />
                <button
                  type="button"
                  disabled={isTestingBackend}
                  onClick={async () => {
                    setIsTestingBackend(true);
                    api.setBaseUrl(backendUrlInput);
                    const probe = await api.probeHealth();
                    setIsTestingBackend(false);
                    if (probe.ok) {
                      setBackendHealthStatus({ ok: true, message: `Connected (${probe.service || "PERCEPTA"})` });
                      setErrorDetails(null);
                      try {
                        const res = await api.getAvailableSources();
                        const all = [...(res.bundled_clips || []), ...(res.uploaded_clips || [])];
                        setAvailableClips(all);
                        if (all.length > 0 && !selectedClip) setSelectedClip(all[0].path);
                      } catch {}
                    } else {
                      setBackendHealthStatus({ ok: false, message: probe.error || "Unreachable" });
                    }
                  }}
                  className="h-9 px-3.5 bg-[#1b2530] hover:bg-[#33f0b4] hover:text-black text-white font-mono text-[10.5px] font-bold rounded-lg transition-colors cursor-pointer flex items-center gap-1.5"
                >
                  {isTestingBackend ? (
                    <>
                      <RefreshCw size={11} className="animate-spin" />
                      <span>TESTING...</span>
                    </>
                  ) : (
                    <span>TEST & APPLY</span>
                  )}
                </button>
              </div>

              <p className="text-[9.5px] text-[#64748b] leading-relaxed">
                For public Vercel deployment testing, specify an HTTPS endpoint (e.g. via Cloudflare Tunnel, ngrok, or cloud VM) to satisfy browser CORS and Mixed Content policies.
              </p>
            </div>
          )}

          {/* Camera / Post Name Input */}
          <div>
            <label className="block text-[#a0aec0] font-mono text-[10.5px] font-bold tracking-wider uppercase mb-1.5">
              CAMERA / POST NAME
            </label>
            <input
              type="text"
              required
              value={cameraName}
              onChange={(e) => setCameraName(e.target.value)}
              placeholder="e.g. Sector 9 North Fence, Checkpoint Alpha"
              className="w-full h-11 bg-[#05070a] border border-[#1e2a38] focus:border-[#33f0b4] text-[#e8ebe6] font-mono text-xs px-4 rounded-xl focus:outline-none placeholder-[#475569] shadow-inner transition-all"
            />
          </div>

          {/* Sensor Modality Cards (3 Selectable Cards) */}
          <div>
            <label className="block text-[#a0aec0] font-mono text-[10.5px] font-bold tracking-wider uppercase mb-2">
              SENSOR MODALITY
            </label>
            <div className="grid grid-cols-3 gap-3">
              {/* Card 1: STANDARD RGB */}
              <button
                type="button"
                onClick={() => setModality("STANDARD")}
                className={`p-3.5 rounded-xl border text-left flex flex-col justify-between transition-all cursor-pointer ${
                  modality === "STANDARD"
                    ? "border-[#33f0b4] bg-[#33f0b4]/10 shadow-[0_0_14px_rgba(51,240,180,0.18)]"
                    : "border-[#1b2530] bg-[#070a0f] hover:border-[#263340] opacity-80 hover:opacity-100"
                }`}
              >
                <div className="flex items-center justify-between w-full mb-2">
                  <Camera
                    size={18}
                    className={modality === "STANDARD" ? "text-[#33f0b4]" : "text-[#869099]"}
                  />
                  <div
                    className={`w-2 h-2 rounded-full ${
                      modality === "STANDARD"
                        ? "bg-[#33f0b4] shadow-[0_0_6px_#33f0b4]"
                        : "bg-transparent border border-[#3b4c60]"
                    }`}
                  />
                </div>
                <div>
                  <h4
                    className={`font-['Chakra_Petch',sans-serif] font-bold text-xs uppercase tracking-wider ${
                      modality === "STANDARD" ? "text-[#33f0b4]" : "text-white"
                    }`}
                  >
                    STANDARD RGB
                  </h4>
                  <p className="text-[10px] font-mono text-[#8b9bb0] mt-0.5">Optical CCTV</p>
                </div>
              </button>

              {/* Card 2: IR NIGHT */}
              <button
                type="button"
                onClick={() => setModality("IR")}
                className={`p-3.5 rounded-xl border text-left flex flex-col justify-between transition-all cursor-pointer ${
                  modality === "IR"
                    ? "border-[#33f0b4] bg-[#33f0b4]/10 shadow-[0_0_14px_rgba(51,240,180,0.18)]"
                    : "border-[#1b2530] bg-[#070a0f] hover:border-[#263340] opacity-80 hover:opacity-100"
                }`}
              >
                <div className="flex items-center justify-between w-full mb-2">
                  <Moon
                    size={18}
                    className={modality === "IR" ? "text-[#33f0b4]" : "text-[#869099]"}
                  />
                  <div
                    className={`w-2 h-2 rounded-full ${
                      modality === "IR"
                        ? "bg-[#33f0b4] shadow-[0_0_6px_#33f0b4]"
                        : "bg-transparent border border-[#3b4c60]"
                    }`}
                  />
                </div>
                <div>
                  <h4
                    className={`font-['Chakra_Petch',sans-serif] font-bold text-xs uppercase tracking-wider ${
                      modality === "IR" ? "text-[#33f0b4]" : "text-white"
                    }`}
                  >
                    IR NIGHT
                  </h4>
                  <p className="text-[10px] font-mono text-[#8b9bb0] mt-0.5">Night Vision</p>
                </div>
              </button>

              {/* Card 3: THERMAL IR */}
              <button
                type="button"
                onClick={() => setModality("THERMAL")}
                className={`p-3.5 rounded-xl border text-left flex flex-col justify-between transition-all cursor-pointer ${
                  modality === "THERMAL"
                    ? "border-[#33f0b4] bg-[#33f0b4]/10 shadow-[0_0_14px_rgba(51,240,180,0.18)]"
                    : "border-[#1b2530] bg-[#070a0f] hover:border-[#263340] opacity-80 hover:opacity-100"
                }`}
              >
                <div className="flex items-center justify-between w-full mb-2">
                  <Flame
                    size={18}
                    className={modality === "THERMAL" ? "text-[#33f0b4]" : "text-[#869099]"}
                  />
                  <div
                    className={`w-2 h-2 rounded-full ${
                      modality === "THERMAL"
                        ? "bg-[#33f0b4] shadow-[0_0_6px_#33f0b4]"
                        : "bg-transparent border border-[#3b4c60]"
                    }`}
                  />
                </div>
                <div>
                  <h4
                    className={`font-['Chakra_Petch',sans-serif] font-bold text-xs uppercase tracking-wider ${
                      modality === "THERMAL" ? "text-[#33f0b4]" : "text-white"
                    }`}
                  >
                    THERMAL IR
                  </h4>
                  <p className="text-[10px] font-mono text-[#8b9bb0] mt-0.5">Heat Radiometry</p>
                </div>
              </button>
            </div>
          </div>

          {/* Segmented Source Selector */}
          <div>
            <label className="block text-[#a0aec0] font-mono text-[10.5px] font-bold tracking-wider uppercase mb-2">
              SOURCE TYPE
            </label>
            <div className="grid grid-cols-3 p-1 bg-[#05070a] border border-[#1b2530] rounded-xl text-xs font-mono">
              <button
                type="button"
                onClick={() => setSourceType("video_file")}
                className={`py-2 px-3 rounded-lg flex items-center justify-center gap-2 transition-all cursor-pointer ${
                  sourceType === "video_file"
                    ? "bg-[#14202c] border border-[#33f0b4]/45 text-[#33f0b4] font-bold shadow-md"
                    : "text-[#869099] hover:text-white border border-transparent"
                }`}
              >
                <Video size={14} />
                <span>Video File</span>
              </button>

              <button
                type="button"
                onClick={() => setSourceType("rtsp")}
                className={`py-2 px-3 rounded-lg flex items-center justify-center gap-2 transition-all cursor-pointer ${
                  sourceType === "rtsp"
                    ? "bg-[#14202c] border border-[#33f0b4]/45 text-[#33f0b4] font-bold shadow-md"
                    : "text-[#869099] hover:text-white border border-transparent"
                }`}
              >
                <Radio size={14} />
                <span>RTSP IP</span>
              </button>

              <button
                type="button"
                onClick={() => setSourceType("webcam")}
                className={`py-2 px-3 rounded-lg flex items-center justify-center gap-2 transition-all cursor-pointer ${
                  sourceType === "webcam"
                    ? "bg-[#14202c] border border-[#33f0b4]/45 text-[#33f0b4] font-bold shadow-md"
                    : "text-[#869099] hover:text-white border border-transparent"
                }`}
              >
                <Camera size={14} />
                <span>Webcam</span>
              </button>
            </div>
          </div>

          {/* ── 3. Source Details Content ── */}
          {sourceType === "video_file" && (
            <div className="space-y-3">
              {/* Large Drag-and-Drop Area Matching Old Screenshot Scale */}
              <div
                onClick={() => fileInputRef.current?.click()}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                className={`relative border-2 border-dashed rounded-2xl py-8 px-6 flex flex-col items-center justify-center text-center cursor-pointer transition-all ${
                  isDragging
                    ? "border-[#33f0b4] bg-[#33f0b4]/15 shadow-[0_0_20px_rgba(51,240,180,0.2)]"
                    : uploadFile
                    ? "border-[#33f0b4]/60 bg-[#070b10]"
                    : "border-[#1e2a38] hover:border-[#33f0b4]/50 bg-[#05070a]/90"
                }`}
              >
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="video/*"
                  onChange={handleFileChange}
                  className="hidden"
                />

                {uploadFile ? (
                  <div className="flex flex-col items-center gap-2 pointer-events-none">
                    <div className="w-12 h-12 rounded-full bg-[#33f0b4]/15 border border-[#33f0b4]/40 flex items-center justify-center text-[#33f0b4]">
                      <FileVideo size={24} />
                    </div>
                    <span className="font-mono text-sm font-bold text-white tracking-wide">
                      {uploadFile.name}
                    </span>
                    <span className="text-[10px] font-mono text-[#33f0b4] bg-[#33f0b4]/10 border border-[#33f0b4]/30 px-2 py-0.5 rounded">
                      {(uploadFile.size / 1024 / 1024).toFixed(2)} MB • READY FOR INGESTION
                    </span>
                    <span className="text-[9px] font-mono text-[#869099] mt-1">
                      Click to choose another file
                    </span>
                  </div>
                ) : (
                  <div className="flex flex-col items-center gap-2 pointer-events-none">
                    <div className="w-12 h-12 rounded-full bg-[#33f0b4]/10 border border-[#33f0b4]/30 flex items-center justify-center text-[#33f0b4] mb-1">
                      <Upload size={22} strokeWidth={2} />
                    </div>
                    <p className="font-mono text-xs font-bold text-white tracking-wide">
                      Drop any video file here or click to browse
                    </p>
                    <p className="font-mono text-[10px] text-[#64748b] max-w-sm">
                      Accepts any video format (MP4, AVI, MOV, MKV, WebM, TS, etc.)
                    </p>
                  </div>
                )}
              </div>

              {/* Bundled Clips Option */}
              {availableClips.length > 0 && (
                <div className="pt-1">
                  <label className="block text-[#8b9bb0] font-mono text-[9.5px] uppercase tracking-wider mb-1">
                    Or select pre-bundled border surveillance dataset:
                  </label>
                  <select
                    value={selectedClip}
                    onChange={(e) => {
                      setSelectedClip(e.target.value);
                      setUploadFile(null);
                    }}
                    className="w-full bg-[#05070a] border border-[#1b2530] rounded-xl px-3.5 py-2 text-white font-mono text-[11px] focus:outline-none focus:border-[#33f0b4] cursor-pointer"
                  >
                    {availableClips.map((c) => (
                      <option key={c.path} value={c.path}>
                        {c.name} ({c.size_mb.toFixed(1)} MB)
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}

          {sourceType === "rtsp" && (
            <div className="space-y-3">
              <div>
                <label className="block text-[#a0aec0] font-mono text-[10.5px] font-bold tracking-wider uppercase mb-1.5">
                  RTSP STREAM URL
                </label>
                <input
                  type="text"
                  required
                  value={rtspUrl}
                  onChange={(e) => setRtspUrl(e.target.value)}
                  placeholder="rtsp://admin:password@192.168.1.100:554/live"
                  className="w-full h-11 bg-[#05070a] border border-[#1e2a38] focus:border-[#33f0b4] text-[#e8ebe6] font-mono text-xs px-4 rounded-xl focus:outline-none placeholder-[#475569] shadow-inner"
                />
                <p className="text-[10px] font-mono text-[#64748b] mt-1.5">
                  Network credentials are auto-masked and encrypted. Auto-reconnect enabled for 24/7 reliability.
                </p>
              </div>
            </div>
          )}

          {sourceType === "webcam" && (
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-[#a0aec0] font-mono text-[10.5px] font-bold tracking-wider uppercase mb-1.5">
                  CAMERA DEVICE INDEX
                </label>
                <input
                  type="number"
                  min="0"
                  max="10"
                  value={deviceIndex}
                  onChange={(e) => setDeviceIndex(parseInt(e.target.value) || 0)}
                  className="w-full h-11 bg-[#05070a] border border-[#1e2a38] focus:border-[#33f0b4] text-[#e8ebe6] font-mono text-xs px-4 rounded-xl focus:outline-none shadow-inner"
                />
                <p className="text-[9.5px] font-mono text-[#64748b] mt-1">
                  Default webcam is <code>0</code>. USB inputs are <code>1</code> or <code>2</code>.
                </p>
              </div>

              <div>
                <label className="block text-[#a0aec0] font-mono text-[10.5px] font-bold tracking-wider uppercase mb-1.5">
                  TARGET PERCEPTION FPS
                </label>
                <input
                  type="number"
                  min="5"
                  max="60"
                  value={fps}
                  onChange={(e) => setFps(parseInt(e.target.value) || 30)}
                  className="w-full h-11 bg-[#05070a] border border-[#1e2a38] focus:border-[#33f0b4] text-[#e8ebe6] font-mono text-xs px-4 rounded-xl focus:outline-none shadow-inner"
                />
              </div>
            </div>
          )}

          {/* ── 4. Modal Footer Actions ── */}
          <div className="flex items-center justify-end gap-3 pt-4 border-t border-[#1b2530]">
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2.5 text-xs font-mono font-bold text-[#869099] hover:text-white hover:bg-white/5 rounded-xl transition-colors cursor-pointer"
            >
              CANCEL
            </button>

            <button
              type="submit"
              disabled={isSubmitting}
              className="h-10 px-6 bg-[#33f0b4] hover:bg-[#28dfa3] text-black font-['Chakra_Petch',sans-serif] font-bold text-xs uppercase tracking-wider rounded-xl flex items-center gap-2 shadow-[0_0_16px_rgba(51,240,180,0.35)] transition-all cursor-pointer disabled:opacity-50 disabled:shadow-none"
            >
              {isSubmitting ? (
                <>
                  <Loader2 size={15} className="animate-spin text-black" />
                  <span>STARTING INGESTION...</span>
                </>
              ) : (
                <>
                  <Check size={15} strokeWidth={2.5} />
                  <span>START INGESTION</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
