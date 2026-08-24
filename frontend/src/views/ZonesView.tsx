import React, { useState, useEffect } from "react";
import { useSurveillance } from "../store/surveillanceContext";
import { api } from "../api/client";
import type { ZoneTemplate } from "../types/surveillance";
import {
  Layers,
  Trash2,
  CheckCircle2,
  Sparkles,
  Plus,
  Radio,
  PenTool,
  RefreshCw,
} from "lucide-react";
import { CameraCard } from "../components/CameraCard";

export const ZonesView: React.FC = () => {
  const { cameras, refreshAll } = useSurveillance();
  const [activeZones, setActiveZones] = useState<any[]>([]);
  const [activeBoundaries, setActiveBoundaries] = useState<any[]>([]);
  const [templates, setTemplates] = useState<ZoneTemplate[]>([]);
  const [selectedCameraId, setSelectedCameraId] = useState<string>(
    cameras[0]?.camera_id || "CAM-01"
  );
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(false);

  const fetchZonesAndTemplates = async () => {
    setIsLoading(true);
    try {
      const [zonesRes, tmplRes] = await Promise.all([
        api.getZones().catch(() => null),
        api.getZoneTemplates().catch(() => null),
      ]);

      if (zonesRes) {
        setActiveZones(zonesRes.zones || []);
        setActiveBoundaries(zonesRes.boundaries || (zonesRes as any).virtual_boundaries || []);
      }
      if (tmplRes?.templates) {
        setTemplates(tmplRes.templates);
      }
    } catch (err) {
      console.error("Failed to fetch zones/templates:", err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchZonesAndTemplates();
  }, []);

  const handleDeleteZone = async (zoneId: string) => {
    if (confirm(`Delete zone / boundary '${zoneId}'?`)) {
      try {
        await api.deleteZone(zoneId);
        setStatusMessage(`Deleted '${zoneId}'.`);
        setTimeout(() => setStatusMessage(null), 3000);
        fetchZonesAndTemplates();
      } catch (err: any) {
        alert(`Failed to delete zone: ${err.message}`);
      }
    }
  };

  const handleApplyTemplate = async (templateId: string, name: string) => {
    try {
      await api.applyZoneTemplate(templateId, Date.now().toString().slice(-3), name);
      setStatusMessage(`Applied template '${name}'! Active on all cameras.`);
      setTimeout(() => setStatusMessage(null), 3500);
      fetchZonesAndTemplates();
    } catch (err: any) {
      alert(`Failed to apply template: ${err.message}`);
    }
  };

  const activeCamera = cameras.find((c) => c.camera_id === selectedCameraId) || cameras[0];

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="flex items-center justify-between flex-wrap gap-3 bg-[#0a0f18] border border-white/10 p-3 rounded-sm">
        <div className="flex items-center gap-2.5">
          <Layers className="w-5 h-5 text-[#00e5ff]" />
          <div>
            <h3 className="font-display font-bold text-base tracking-wider text-white">
              SECURITY ZONES & VIRTUAL TRIPWIRES
            </h3>
            <p className="font-mono-tech text-[11px] text-gray-400">
              Deterministic point-in-polygon containment & vector line-crossing rules
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {statusMessage && (
            <div className="px-3 py-1 bg-emerald-500/20 text-[#00e676] border border-emerald-500/40 rounded text-xs font-mono-tech flex items-center gap-1.5 animate-fade-in">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>{statusMessage}</span>
            </div>
          )}

          <button
            onClick={fetchZonesAndTemplates}
            className="p-1.5 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded transition-colors"
            title="Refresh Zones"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Main Layout Grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column (7 cols): Camera Video Card with In-Place Drawing */}
        <div className="col-span-12 lg:col-span-7 space-y-3">
          {/* Camera Picker */}
          <div className="flex items-center justify-between bg-[#0a0f18] border border-white/10 p-2.5 rounded-sm">
            <div className="flex items-center gap-2 font-mono-tech text-xs text-gray-300">
              <Radio className="w-3.5 h-3.5 text-[#00e5ff]" />
              <span>DRAW ON CAMERA:</span>
            </div>
            <div className="flex items-center gap-1.5 overflow-x-auto">
              {cameras.map((c) => (
                <button
                  key={c.camera_id}
                  onClick={() => setSelectedCameraId(c.camera_id)}
                  className={`px-2.5 py-1 text-[11px] font-mono-tech font-bold rounded flex items-center gap-1 transition-all ${
                    selectedCameraId === c.camera_id
                      ? "bg-[#00e5ff]/20 text-[#00e5ff] border border-[#00e5ff]/50"
                      : "bg-white/5 text-gray-400 border border-white/10 hover:text-white"
                  }`}
                >
                  {c.camera_id}
                </button>
              ))}
            </div>
          </div>

          {/* Camera Card with In-Place Drawing Canvas */}
          {activeCamera ? (
            <div className="min-h-[420px]">
              <CameraCard
                camera={activeCamera}
                onRefresh={() => {
                  fetchZonesAndTemplates();
                  refreshAll();
                }}
              />
            </div>
          ) : (
            <div className="p-8 bg-[#090d14] border border-white/10 rounded text-center text-gray-500 font-mono-tech text-xs">
              No active camera available to draw zones on.
            </div>
          )}

          {/* Quick Guidance Box */}
          <div className="p-3 bg-[#060a12] border border-white/10 rounded text-xs font-mono-tech text-gray-400 space-y-1">
            <div className="text-gray-200 font-bold flex items-center gap-1">
              <PenTool className="w-3.5 h-3.5 text-[#00e5ff]" />
              <span>How to Draw Zones:</span>
            </div>
            <p>
              1. Click <strong>ZONE</strong> or <strong>TRIPWIRE</strong> in the top-right of the video tile above.
            </p>
            <p>
              2. Click on the video feed to place vertices (≥3 for polygon, 2 for tripwire). Clicks are converted to source-frame pixel coordinates automatically.
            </p>
            <p>
              3. Set Severity / Loitering threshold and click <strong>SAVE</strong>. The rule activates immediately on the live stream!
            </p>
          </div>
        </div>

        {/* Right Column (5 cols): Active Zones List + Quick Tactical Templates */}
        <div className="col-span-12 lg:col-span-5 space-y-4">
          {/* Active Rules List */}
          <div className="bg-[#090d14] border border-white/10 rounded-sm overflow-hidden flex flex-col">
            <div className="px-4 py-3 bg-[#0e141f] border-b border-white/10 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-[#00e5ff]" />
                <h4 className="font-display font-bold text-sm text-white">
                  ACTIVE ZONES & TRIPWIRES
                </h4>
              </div>
              <span className="text-[10px] font-mono-tech px-2 py-0.5 bg-white/5 border border-white/10 rounded text-gray-300">
                {activeZones.length + activeBoundaries.length} RULES CONFIGURED
              </span>
            </div>

            <div className="p-3 overflow-y-auto space-y-2.5 max-h-[300px]">
              {activeZones.length > 0 || activeBoundaries.length > 0 ? (
                <>
                  {/* Polygon Zones */}
                  {activeZones.map((z) => (
                    <div
                      key={z.zone_id}
                      className="p-3 bg-[#060a12] border border-white/10 rounded flex items-center justify-between gap-3"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-display font-bold text-xs text-white">
                            {z.name}
                          </span>
                          <span
                            className={`text-[9px] font-mono-tech font-bold px-1.5 py-0.2 rounded uppercase ${
                              z.severity?.toUpperCase() === "CRITICAL"
                                ? "bg-red-500/20 text-red-400 border border-red-500/30"
                                : "bg-amber-500/20 text-amber-400 border border-amber-500/30"
                            }`}
                          >
                            {z.severity}
                          </span>
                        </div>
                        <div className="font-mono-tech text-[10px] text-gray-400 mt-1">
                          ID: <code>{z.zone_id}</code> • {z.polygon?.length || 0} Vertices • Dwell: {z.loitering_threshold_seconds || 0}s
                        </div>
                      </div>

                      <button
                        onClick={() => handleDeleteZone(z.zone_id)}
                        className="p-1.5 bg-red-500/10 hover:bg-red-500/25 text-red-400 border border-red-500/30 rounded transition-colors"
                        title="Delete Zone"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}

                  {/* Virtual Tripwires */}
                  {activeBoundaries.map((b) => (
                    <div
                      key={b.boundary_id}
                      className="p-3 bg-[#060a12] border border-white/10 rounded flex items-center justify-between gap-3"
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-display font-bold text-xs text-[#ffab00]">
                            {b.name}
                          </span>
                          <span className="text-[9px] font-mono-tech font-bold px-1.5 py-0.2 bg-amber-500/20 text-amber-400 border border-amber-500/30 rounded uppercase">
                            TRIPWIRE
                          </span>
                        </div>
                        <div className="font-mono-tech text-[10px] text-gray-400 mt-1">
                          ID: <code>{b.boundary_id}</code> • pt1: [{b.pt1?.join(",")}] → pt2: [{b.pt2?.join(",")}]
                        </div>
                      </div>

                      <button
                        onClick={() => handleDeleteZone(b.boundary_id)}
                        className="p-1.5 bg-red-500/10 hover:bg-red-500/25 text-red-400 border border-red-500/30 rounded transition-colors"
                        title="Delete Tripwire"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  ))}
                </>
              ) : (
                <div className="p-6 text-center text-gray-500 font-mono-tech text-xs">
                  No zones configured. Draw a zone on the video or apply a tactical template below.
                </div>
              )}
            </div>
          </div>

          {/* Tactical Templates */}
          {templates.length > 0 && (
            <div className="bg-[#090d14] border border-white/10 rounded-sm overflow-hidden flex flex-col">
              <div className="px-4 py-3 bg-[#0e141f] border-b border-white/10 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Sparkles className="w-4 h-4 text-[#ffab00]" />
                  <h4 className="font-display font-bold text-sm text-white">
                    1-CLICK TACTICAL TEMPLATES
                  </h4>
                </div>
                <span className="text-[10px] font-mono-tech text-gray-400">
                  Pre-configured defense geometries
                </span>
              </div>

              <div className="p-3 space-y-2 max-h-[300px] overflow-y-auto">
                {templates.map((tmpl) => (
                  <div
                    key={tmpl.template_id}
                    className="p-2.5 bg-[#060a12] border border-white/10 rounded flex items-center justify-between gap-3"
                  >
                    <div>
                      <span className="font-display font-bold text-xs text-white block">
                        {tmpl.name}
                      </span>
                      <p className="text-[10px] text-gray-400 font-sans line-clamp-1">
                        {tmpl.description}
                      </p>
                    </div>

                    <button
                      onClick={() => handleApplyTemplate(tmpl.template_id, tmpl.name)}
                      className="px-2.5 py-1 bg-[#ffab00]/15 hover:bg-[#ffab00]/30 text-[#ffab00] border border-[#ffab00]/40 text-xs font-display font-bold rounded flex items-center gap-1 shrink-0 transition-colors"
                    >
                      <Plus className="w-3 h-3" />
                      <span>DEPLOY</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
