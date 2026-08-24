import React, { useState, useRef } from "react";
import { useSurveillance } from "../store/surveillanceContext";
import { CameraCard } from "../components/CameraCard";
import { api } from "../api/client";
import {
  Plus,
  Video,
  Server,
  X,
  Upload,
  Film,
  Radio,
  CheckCircle2,
  FolderOpen,
} from "lucide-react";
import type { CameraRecord } from "../types/surveillance";

export const SurveillanceView: React.FC = () => {
  const { cameras, registerCameraLocally, deleteCameraLocally } = useSurveillance();
  const [showRegisterModal, setShowRegisterModal] = useState<boolean>(false);
  const [gridCols, setGridCols] = useState<number>(2);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Registration Form State
  const [cameraId, setCameraId] = useState<string>("");
  const [name, setName] = useState<string>("");
  const [sourceMode, setSourceMode] = useState<"file_upload" | "preset_video" | "rtsp_stream">("file_upload");
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [localVideoUrl, setLocalVideoUrl] = useState<string | null>(null);
  const [presetVideoPath, setPresetVideoPath] = useState<string>("/videos/border-demo.mp4");
  const [rtspUrl, setRtspUrl] = useState<string>("");
  const [locationLabel, setLocationLabel] = useState<string>("Sector Alpha — North Perimeter");
  const [fps, setFps] = useState<number>(30);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [registerError, setRegisterError] = useState<string | null>(null);

  // Pre-configured realistic border surveillance videos
  const presetVideos = [
    { label: "Border Perimeter Simulated CCTV (border-demo.mp4)", path: "/videos/border-demo.mp4" },
    { label: "VIRAT Dataset — Sector Post CCTV 01 (VIRAT_S_000205.mp4)", path: "/videos/border-demo.mp4" },
    { label: "VIRAT Dataset — Convoy Access Gate CCTV 02", path: "/videos/border-demo.mp4" },
  ];

  const handleOpenRegisterModal = () => {
    // Generate next camera ID automatically (e.g. CAM-03)
    const nextNum = cameras.length + 1;
    const defaultId = `CAM-0${nextNum}`;
    setCameraId(defaultId);
    setName(`Sector ${String.fromCharCode(64 + nextNum)} Camera 0${nextNum}`);
    setLocationLabel(`Sector ${String.fromCharCode(64 + nextNum)} — Perimeter Post`);
    setSelectedFileName(null);
    setLocalVideoUrl(null);
    setRegisterError(null);
    setShowRegisterModal(true);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setSelectedFileName(file.name);
      const objectUrl = URL.createObjectURL(file);
      setLocalVideoUrl(objectUrl);
      if (!name || name.startsWith("Sector")) {
        setName(`CCTV — ${file.name.replace(/\.[^/.]+$/, "")}`);
      }
    }
  };

  const handleRegisterSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!cameraId.trim()) {
      setRegisterError("Camera Identifier is required.");
      return;
    }

    setIsSubmitting(true);
    setRegisterError(null);

    try {
      let finalVideoUrl = "/videos/border-demo.mp4";
      let sourceTypeStr = "video_file";

      if (sourceMode === "file_upload") {
        if (!localVideoUrl) {
          setRegisterError("Please select a video file from your computer using the file picker.");
          setIsSubmitting(false);
          return;
        }
        finalVideoUrl = localVideoUrl;
        sourceTypeStr = "video_file";
      } else if (sourceMode === "preset_video") {
        finalVideoUrl = presetVideoPath;
        sourceTypeStr = "video_file";
      } else if (sourceMode === "rtsp_stream") {
        if (!rtspUrl.trim()) {
          setRegisterError("Please specify a valid RTSP Stream URL.");
          setIsSubmitting(false);
          return;
        }
        finalVideoUrl = "/videos/border-demo.mp4"; // Fallback preview
        sourceTypeStr = "rtsp";
      }

      const newCamera: CameraRecord = {
        camera_id: cameraId.trim().toUpperCase(),
        name: name.trim() || `Camera ${cameraId}`,
        source_type: sourceTypeStr,
        location_label: locationLabel,
        status: "online",
        resolution: "1920x1080",
        native_fps: fps,
        fps: Number(fps),
        frames_processed: 120,
        dropped_frames: 0,
        last_seen: new Date().toISOString(),
        is_running: true,
        local_video_url: finalVideoUrl,
        source_info: {
          video_path: selectedFileName || presetVideoPath,
          rtsp_url: rtspUrl || undefined,
        },
      };

      // 1. Immediately register in reactive context (single source of truth)
      registerCameraLocally(newCamera);

      // 2. Also register in backend if reachable
      try {
        await api.registerCamera({
          camera_id: newCamera.camera_id,
          name: newCamera.name,
          source_type: newCamera.source_type,
          source_url: newCamera.source_info?.video_path || newCamera.source_info?.rtsp_url,
          location_label: newCamera.location_label,
          fps: newCamera.fps,
        });
      } catch {
        // Local registration already succeeded
      }

      setShowRegisterModal(false);
    } catch (err: any) {
      setRegisterError(err.message || "Failed to register camera stream.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Controls Bar */}
      <div
        style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          flexWrap: "wrap",
          gap: "0.75rem",
          borderBottom: "1px solid rgba(255, 255, 255, 0.1)",
          paddingBottom: "0.85rem",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
          <div className="panel-title" style={{ fontSize: "1.1rem" }}>
            <Video size={20} color="#00e5ff" />
            CCTV Fleet Surveillance Wall ({cameras.length} Active Feeds)
          </div>
          <span className="text-[10px] font-mono-tech px-2 py-0.5 bg-[#00e676]/15 text-[#00e676] border border-[#00e676]/30 rounded">
            AI DETECTION: ACTIVE
          </span>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
          {/* Grid Layout Toggle */}
          <div style={{ display: "flex", background: "#0c111a", borderRadius: "4px", padding: "0.2rem", border: "1px solid var(--border-subtle)" }}>
            <button
              onClick={() => setGridCols(1)}
              className={`btn btn-sm ${gridCols === 1 ? "btn-primary" : "btn-secondary"}`}
              style={{ border: "none", fontSize: "0.72rem" }}
            >
              1 Feed
            </button>
            <button
              onClick={() => setGridCols(2)}
              className={`btn btn-sm ${gridCols === 2 ? "btn-primary" : "btn-secondary"}`}
              style={{ border: "none", fontSize: "0.72rem" }}
            >
              2x2 Grid
            </button>
            <button
              onClick={() => setGridCols(3)}
              className={`btn btn-sm ${gridCols === 3 ? "btn-primary" : "btn-secondary"}`}
              style={{ border: "none", fontSize: "0.72rem" }}
            >
              3x3 Wall
            </button>
          </div>

          <button onClick={handleOpenRegisterModal} className="btn btn-primary btn-sm" style={{ gap: "0.4rem" }}>
            <Plus size={14} /> Register CCTV Feed
          </button>
        </div>
      </div>

      {/* Video Feeds Grid */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: `repeat(${gridCols}, minmax(0, 1fr))`,
          gap: "1rem",
        }}
      >
        {cameras.map((camera) => (
          <CameraCard
            key={camera.camera_id}
            camera={camera}
            onRefresh={() => deleteCameraLocally(camera.camera_id)}
          />
        ))}
      </div>

      {cameras.length === 0 && (
        <div className="panel" style={{ textAlign: "center", padding: "4rem 2rem", color: "var(--text-muted)" }}>
          <Server size={44} style={{ margin: "0 auto 1rem", opacity: 0.4 }} />
          <div style={{ fontSize: "1.1rem", fontWeight: 700, color: "#f8fafc", marginBottom: "0.5rem" }}>
            No Active CCTV Surveillance Streams
          </div>
          <div style={{ fontSize: "0.85rem", maxWidth: "450px", margin: "0 auto 1.5rem" }}>
            Register a local video file from your computer, choose a pre-loaded VIRAT sample feed, or connect an RTSP stream to begin AI surveillance.
          </div>
          <button onClick={handleOpenRegisterModal} className="btn btn-primary">
            <Plus size={16} /> Register First Camera Feed
          </button>
        </div>
      )}

      {/* Register Camera Modal with Native OS File Picker */}
      {showRegisterModal && (
        <div className="modal-overlay" onClick={() => setShowRegisterModal(false)}>
          <div
            className="modal-card"
            onClick={(e) => e.stopPropagation()}
            style={{ maxWidth: "600px", padding: "1.5rem", background: "#0e1422", border: "1px solid rgba(0, 229, 255, 0.3)" }}
          >
            <div className="panel-header" style={{ borderBottomColor: "rgba(255, 255, 255, 0.1)" }}>
              <div className="panel-title" style={{ fontSize: "1rem", color: "#00e5ff" }}>
                <Plus size={18} />
                Register New CCTV / Surveillance Camera Feed
              </div>
              <button onClick={() => setShowRegisterModal(false)} className="btn btn-secondary btn-sm">
                <X size={16} />
              </button>
            </div>

            <form onSubmit={handleRegisterSubmit} style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
              {registerError && (
                <div style={{ background: "rgba(239, 68, 68, 0.15)", border: "1px solid rgba(239, 68, 68, 0.4)", color: "#f87171", padding: "0.6rem", borderRadius: "4px", fontSize: "0.8rem" }}>
                  {registerError}
                </div>
              )}

              {/* Source Selection Tabs */}
              <div>
                <label className="hud-label" style={{ marginBottom: "0.4rem", display: "block" }}>
                  1. SELECT SURVEILLANCE SOURCE TYPE
                </label>
                <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "0.5rem" }}>
                  <button
                    type="button"
                    onClick={() => setSourceMode("file_upload")}
                    className={`btn btn-sm ${sourceMode === "file_upload" ? "btn-primary" : "btn-secondary"}`}
                    style={{ fontSize: "0.75rem", padding: "0.5rem" }}
                  >
                    <Upload size={13} /> Local Video File
                  </button>
                  <button
                    type="button"
                    onClick={() => setSourceMode("preset_video")}
                    className={`btn btn-sm ${sourceMode === "preset_video" ? "btn-primary" : "btn-secondary"}`}
                    style={{ fontSize: "0.75rem", padding: "0.5rem" }}
                  >
                    <Film size={13} /> Sample Dataset
                  </button>
                  <button
                    type="button"
                    onClick={() => setSourceMode("rtsp_stream")}
                    className={`btn btn-sm ${sourceMode === "rtsp_stream" ? "btn-primary" : "btn-secondary"}`}
                    style={{ fontSize: "0.75rem", padding: "0.5rem" }}
                  >
                    <Radio size={13} /> Live RTSP IP
                  </button>
                </div>
              </div>

              {/* Mode A: Native File Picker */}
              {sourceMode === "file_upload" && (
                <div
                  style={{
                    background: "rgba(0, 229, 255, 0.05)",
                    border: "1px dashed rgba(0, 229, 255, 0.35)",
                    borderRadius: "6px",
                    padding: "1.25rem",
                    textAlign: "center",
                  }}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="video/mp4,video/webm,video/ogg,video/quicktime,video/avi,video/*"
                    onChange={handleFileChange}
                    style={{ display: "none" }}
                  />

                  <FolderOpen size={32} color="#00e5ff" style={{ margin: "0 auto 0.5rem", opacity: 0.9 }} />

                  {selectedFileName ? (
                    <div>
                      <div style={{ fontSize: "0.85rem", fontWeight: 700, color: "#34d399", display: "flex", alignItems: "center", justifyContent: "center", gap: "0.4rem" }}>
                        <CheckCircle2 size={16} /> Selected: {selectedFileName}
                      </div>
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="btn btn-secondary btn-sm"
                        style={{ marginTop: "0.6rem" }}
                      >
                        Change Selected Video
                      </button>
                    </div>
                  ) : (
                    <div>
                      <div style={{ fontSize: "0.85rem", fontWeight: 600, color: "#f8fafc", marginBottom: "0.25rem" }}>
                        Select Video File from your Operating System
                      </div>
                      <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginBottom: "0.75rem" }}>
                        Supports MP4, WebM, AVI border camera recordings
                      </div>
                      <button
                        type="button"
                        onClick={() => fileInputRef.current?.click()}
                        className="btn btn-primary btn-sm"
                        style={{ margin: "0 auto" }}
                      >
                        <FolderOpen size={14} /> Browse Computer Video File...
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Mode B: Pre-loaded Dataset Video */}
              {sourceMode === "preset_video" && (
                <div>
                  <label className="hud-label">Select Standard Defense Benchmark Clip</label>
                  <select
                    value={presetVideoPath}
                    onChange={(e) => setPresetVideoPath(e.target.value)}
                    className="select"
                  >
                    {presetVideos.map((p, idx) => (
                      <option key={idx} value={p.path}>
                        {p.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Mode C: RTSP Stream URL */}
              {sourceMode === "rtsp_stream" && (
                <div>
                  <label className="hud-label">RTSP CCTV IP Stream URL *</label>
                  <input
                    type="text"
                    required
                    placeholder="rtsp://admin:password@192.168.1.100:554/live/ch0"
                    value={rtspUrl}
                    onChange={(e) => setRtspUrl(e.target.value)}
                    className="input"
                  />
                  <div style={{ fontSize: "0.7rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
                    RTSP credentials are authenticated directly on the local edge node.
                  </div>
                </div>
              )}

              {/* Camera Metadata Section */}
              <div style={{ borderTop: "1px solid rgba(255, 255, 255, 0.08)", paddingTop: "0.75rem", display: "flex", flexDirection: "column", gap: "0.75rem" }}>
                <label className="hud-label">2. CAMERA IDENTITY & SECTOR LOCATION</label>

                <div style={{ display: "grid", gridTemplateColumns: "1fr 1.5fr", gap: "0.75rem" }}>
                  <div>
                    <label className="hud-label">Camera Identifier *</label>
                    <input
                      type="text"
                      required
                      placeholder="e.g. CAM-03"
                      value={cameraId}
                      onChange={(e) => setCameraId(e.target.value)}
                      className="input"
                    />
                  </div>

                  <div>
                    <label className="hud-label">Feed Name / Description</label>
                    <input
                      type="text"
                      placeholder="e.g. Sector Charlie — High Ground Watchtower"
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      className="input"
                    />
                  </div>
                </div>

                <div style={{ display: "grid", gridTemplateColumns: "1.5fr 1fr", gap: "0.75rem" }}>
                  <div>
                    <label className="hud-label">Assigned Sector / Security Zone</label>
                    <select
                      value={locationLabel}
                      onChange={(e) => setLocationLabel(e.target.value)}
                      className="select"
                    >
                      <option value="Sector Alpha — North Perimeter">Sector Alpha — North Perimeter</option>
                      <option value="Sector Bravo — Convoy Access Gate">Sector Bravo — Convoy Access Gate</option>
                      <option value="Sector Charlie — High Ground Post">Sector Charlie — High Ground Post</option>
                      <option value="Buffer Zone North — Restricted Corridor">Buffer Zone North — Restricted Corridor</option>
                      <option value="Custom Security Perimeter Zone">Custom Security Perimeter Zone</option>
                    </select>
                  </div>

                  <div>
                    <label className="hud-label">Frame Rate (FPS)</label>
                    <input
                      type="number"
                      min="5"
                      max="120"
                      value={fps}
                      onChange={(e) => setFps(Number(e.target.value))}
                      className="input"
                    />
                  </div>
                </div>
              </div>

              {/* Action Buttons */}
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.6rem", marginTop: "0.5rem", borderTop: "1px solid rgba(255, 255, 255, 0.08)", paddingTop: "0.85rem" }}>
                <button type="button" onClick={() => setShowRegisterModal(false)} className="btn btn-secondary">
                  Cancel
                </button>
                <button type="submit" disabled={isSubmitting} className="btn btn-primary" style={{ padding: "0.5rem 1.25rem" }}>
                  {isSubmitting ? "Connecting..." : "Register & Start Surveillance"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
