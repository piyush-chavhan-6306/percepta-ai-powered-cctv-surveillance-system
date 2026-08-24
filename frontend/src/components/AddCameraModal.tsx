import React, { useState, useEffect } from "react";
import { api } from "../api/client";
import type { CameraRecord } from "../types/surveillance";
import { Video, Camera, Radio, Upload, X, Check, AlertCircle, Loader2 } from "lucide-react";

interface AddCameraModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCameraAdded: (camera: CameraRecord) => void;
}

export const AddCameraModal: React.FC<AddCameraModalProps> = ({
  isOpen,
  onClose,
  onCameraAdded,
}) => {
  const [activeTab, setActiveTab] = useState<"clip" | "webcam" | "rtsp">("clip");
  const [cameraId, setCameraId] = useState("");
  const [cameraName, setCameraName] = useState("");
  const [locationLabel, setLocationLabel] = useState("Sector Alpha Perimeter");
  const [fps, setFps] = useState<number>(30);
  const [deviceIndex, setDeviceIndex] = useState<number>(0);
  const [rtspUrl, setRtspUrl] = useState("");
  const [selectedClip, setSelectedClip] = useState("");
  const [availableClips, setAvailableClips] = useState<Array<{ name: string; path: string; size_mb: number }>>([]);
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      setError(null);
      const randomId = `CAM-${Math.floor(10 + Math.random() * 90)}`;
      setCameraId(randomId);
      setCameraName(`Perimeter Post ${randomId.replace("CAM-", "")}`);

      api.getAvailableSources()
        .then((res) => {
          const all = [...(res.bundled_clips || []), ...(res.uploaded_clips || [])];
          setAvailableClips(all);
          if (all.length > 0) {
            setSelectedClip(all[0].path);
          }
        })
        .catch(() => {});
    }
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setError(null);

    try {
      if (activeTab === "clip") {
        if (uploadFile) {
          const formData = new FormData();
          formData.append("file", uploadFile);
          formData.append("camera_id", cameraId);
          formData.append("name", cameraName);
          formData.append("location_label", locationLabel);
          formData.append("loop", "true");
          const created = await api.uploadCameraVideo(formData);
          onCameraAdded(created);
          onClose();
          return;
        }

        if (!selectedClip) {
          throw new Error("Please select a video clip or upload footage.");
        }

        const created = await api.registerCamera({
          camera_id: cameraId,
          name: cameraName,
          source_type: "video_file",
          source_url: selectedClip,
          location_label: locationLabel,
          fps: fps,
          loop: true,
          autostart: true,
        });
        onCameraAdded(created);
        onClose();
      } else if (activeTab === "webcam") {
        const created = await api.registerCamera({
          camera_id: cameraId,
          name: cameraName || `Webcam ${deviceIndex}`,
          source_type: "webcam",
          source_url: deviceIndex.toString(),
          device_index: deviceIndex,
          location_label: locationLabel,
          fps: fps,
          autostart: true,
        });
        onCameraAdded(created);
        onClose();
      } else if (activeTab === "rtsp") {
        if (!rtspUrl.trim()) {
          throw new Error("RTSP stream URL is required (e.g. rtsp://192.168.1.50:554/live)");
        }
        const created = await api.registerCamera({
          camera_id: cameraId,
          name: cameraName || "RTSP Stream",
          source_type: "rtsp",
          source_url: rtspUrl.trim(),
          location_label: locationLabel,
          fps: fps,
          autostart: true,
        });
        onCameraAdded(created);
        onClose();
      }
    } catch (err: any) {
      setError(err.message || "Failed to register camera");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4">
      <div className="bg-[#0b1019] border border-white/15 rounded-md w-full max-w-lg shadow-2xl overflow-hidden flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-white/10 bg-[#0e1522]">
          <div className="flex items-center gap-2.5">
            <Camera className="w-5 h-5 text-[#00e5ff]" />
            <h3 className="font-display font-bold text-base tracking-wide text-white">
              ADD SURVEILLANCE CAMERA
            </h3>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-1 rounded transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Morphic Tabs */}
        <div className="grid grid-cols-3 border-b border-white/10 bg-[#070b12] text-xs font-display font-semibold">
          <button
            type="button"
            onClick={() => setActiveTab("clip")}
            className={`py-3 px-4 flex items-center justify-center gap-2 border-b-2 transition-all ${
              activeTab === "clip"
                ? "border-[#00e5ff] text-[#00e5ff] bg-white/5"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <Video className="w-4 h-4" />
            <span>VIDEO / DATASET</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("webcam")}
            className={`py-3 px-4 flex items-center justify-center gap-2 border-b-2 transition-all ${
              activeTab === "webcam"
                ? "border-[#00e5ff] text-[#00e5ff] bg-white/5"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <Camera className="w-4 h-4" />
            <span>WEBCAM (LIVE 24/7)</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("rtsp")}
            className={`py-3 px-4 flex items-center justify-center gap-2 border-b-2 transition-all ${
              activeTab === "rtsp"
                ? "border-[#00e5ff] text-[#00e5ff] bg-white/5"
                : "border-transparent text-gray-400 hover:text-gray-200"
            }`}
          >
            <Radio className="w-4 h-4" />
            <span>RTSP IP STREAM</span>
          </button>
        </div>

        {/* Form Body */}
        <form onSubmit={handleSubmit} className="p-5 space-y-4 text-xs font-sans">
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/30 rounded text-red-400 text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-gray-400 font-mono-tech text-[11px] mb-1">
                CAMERA ID
              </label>
              <input
                type="text"
                required
                value={cameraId}
                onChange={(e) => setCameraId(e.target.value)}
                placeholder="e.g. CAM-02"
                className="w-full bg-[#070a10] border border-white/10 rounded px-3 py-2 text-white font-mono-tech focus:outline-none focus:border-[#00e5ff]"
              />
            </div>
            <div>
              <label className="block text-gray-400 font-mono-tech text-[11px] mb-1">
                CAMERA NAME
              </label>
              <input
                type="text"
                required
                value={cameraName}
                onChange={(e) => setCameraName(e.target.value)}
                placeholder="e.g. Sector Alpha Gate"
                className="w-full bg-[#070a10] border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-[#00e5ff]"
              />
            </div>
          </div>

          <div>
            <label className="block text-gray-400 font-mono-tech text-[11px] mb-1">
              SECTOR / LOCATION LABEL
            </label>
            <input
              type="text"
              value={locationLabel}
              onChange={(e) => setLocationLabel(e.target.value)}
              placeholder="e.g. Sector Alpha Perimeter"
              className="w-full bg-[#070a10] border border-white/10 rounded px-3 py-2 text-white focus:outline-none focus:border-[#00e5ff]"
            />
          </div>

          {/* Tab Specific Content */}
          {activeTab === "clip" && (
            <div className="space-y-3 pt-1">
              <div>
                <label className="block text-gray-400 font-mono-tech text-[11px] mb-1">
                  CHOOSE BUNDLED FOOTAGE / DATASET
                </label>
                <select
                  value={selectedClip}
                  onChange={(e) => {
                    setSelectedClip(e.target.value);
                    setUploadFile(null);
                  }}
                  className="w-full bg-[#070a10] border border-white/10 rounded px-3 py-2 text-white font-mono-tech focus:outline-none focus:border-[#00e5ff]"
                >
                  {availableClips.map((c) => (
                    <option key={c.path} value={c.path}>
                      {c.name} ({c.size_mb.toFixed(1)} MB)
                    </option>
                  ))}
                </select>
              </div>

              <div className="relative flex items-center justify-center border border-dashed border-white/15 rounded-md p-4 bg-[#070a10] hover:border-[#00e5ff]/50 transition-colors">
                <input
                  type="file"
                  accept="video/*"
                  onChange={(e) => {
                    if (e.target.files?.[0]) {
                      setUploadFile(e.target.files[0]);
                      setSelectedClip("");
                    }
                  }}
                  className="absolute inset-0 opacity-0 cursor-pointer"
                />
                <div className="flex flex-col items-center gap-1.5 text-center pointer-events-none">
                  <Upload className="w-5 h-5 text-gray-400" />
                  <span className="text-gray-300 font-medium">
                    {uploadFile ? uploadFile.name : "Or drag & drop / browse an MP4/WebM file"}
                  </span>
                  <span className="text-gray-500 text-[10px]">
                    {uploadFile ? `${(uploadFile.size / 1024 / 1024).toFixed(2)} MB selected` : "Direct multipart upload to server"}
                  </span>
                </div>
              </div>
            </div>
          )}

          {activeTab === "webcam" && (
            <div className="space-y-3 pt-1">
              <div>
                <label className="block text-gray-400 font-mono-tech text-[11px] mb-1">
                  CAMERA DEVICE INDEX
                </label>
                <input
                  type="number"
                  min="0"
                  max="10"
                  value={deviceIndex}
                  onChange={(e) => setDeviceIndex(parseInt(e.target.value) || 0)}
                  className="w-full bg-[#070a10] border border-white/10 rounded px-3 py-2 text-white font-mono-tech focus:outline-none focus:border-[#00e5ff]"
                />
                <p className="text-[10px] text-gray-500 mt-1">
                  Default laptop webcam is usually device index <code>0</code>. USB cameras are typically <code>1</code> or <code>2</code>.
                </p>
              </div>

              <div>
                <label className="block text-gray-400 font-mono-tech text-[11px] mb-1">
                  TARGET PERCEPTION FPS
                </label>
                <input
                  type="number"
                  min="5"
                  max="60"
                  value={fps}
                  onChange={(e) => setFps(parseInt(e.target.value) || 30)}
                  className="w-full bg-[#070a10] border border-white/10 rounded px-3 py-2 text-white font-mono-tech focus:outline-none focus:border-[#00e5ff]"
                />
              </div>
            </div>
          )}

          {activeTab === "rtsp" && (
            <div className="space-y-3 pt-1">
              <div>
                <label className="block text-gray-400 font-mono-tech text-[11px] mb-1">
                  RTSP STREAM URL
                </label>
                <input
                  type="text"
                  required
                  value={rtspUrl}
                  onChange={(e) => setRtspUrl(e.target.value)}
                  placeholder="rtsp://admin:password@192.168.1.100:554/live"
                  className="w-full bg-[#070a10] border border-white/10 rounded px-3 py-2 text-white font-mono-tech focus:outline-none focus:border-[#00e5ff]"
                />
                <p className="text-[10px] text-gray-500 mt-1">
                  Credentials are encrypted and auto-masked in the UI. Auto-reconnect enabled for 24/7 reliability.
                </p>
              </div>
            </div>
          )}

          {/* Footer Actions */}
          <div className="flex items-center justify-end gap-3 pt-3 border-t border-white/10">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-white/5 hover:bg-white/10 text-gray-300 rounded font-display font-semibold transition-colors"
            >
              CANCEL
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 bg-[#00e5ff] hover:bg-[#00cce6] text-black rounded font-display font-bold flex items-center gap-1.5 transition-all shadow-[0_0_12px_rgba(0,229,255,0.35)]"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>STARTING PERCEPTION...</span>
                </>
              ) : (
                <>
                  <Check className="w-4 h-4" />
                  <span>REGISTER & START PERCEPTION</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
