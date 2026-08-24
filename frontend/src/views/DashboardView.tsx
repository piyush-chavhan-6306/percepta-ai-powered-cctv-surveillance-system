import React, { useState, useEffect } from 'react';
import { useSurveillance } from '../store/surveillanceContext';
import { TacticalMap3D } from '../components/TacticalMap3D';
import { CameraCard } from '../components/CameraCard';
import { AlertTicker } from '../components/AlertTicker';
import { api } from '../api/client';
import type { SecurityZone } from '../types/surveillance';
import {
  Server,
  Zap,
  Layers,
  Eye,
  Plus,
  Play,
  ArrowRight,
  Activity,
} from 'lucide-react';

export const DashboardView: React.FC = () => {
  const {
    cameras,
    threat,
    metrics,
    alerts,
    setActiveView,
    refreshAll,
  } = useSurveillance();

  const [zones, setZones] = useState<SecurityZone[]>([]);
  const [selectedCamId, setSelectedCamId] = useState<string | null>(cameras[0]?.camera_id ?? null);
  const activeCamera = cameras.find((c) => c.camera_id === selectedCamId) ?? cameras[0];

  useEffect(() => {
    api.getZones().then((res) => setZones(res.zones || [])).catch(() => {});
  }, []);

  return (
    <div className="space-y-4">
      {/* Top Welcome / Mission Quick Bar */}
      <div className="panel p-3 flex justify-between items-center flex-wrap gap-3 bg-[#0a0e17] border border-white/10">
        <div>
          <div className="font-display font-bold text-sm text-white flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-[#00e676] animate-pulse" />
            BORDER INTELLIGENCE C2 COMMAND OVERVIEW
          </div>
          <p className="text-[11px] font-mono-tech text-gray-400 mt-0.5">
            Single-pane-of-glass overview across registered CCTV cameras, active detections, and security incidents
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveView('surveillance')}
            className="btn btn-secondary btn-sm"
            style={{ fontSize: '0.75rem', gap: '0.3rem' }}
          >
            <Plus size={13} /> Register New CCTV
          </button>
          <button
            onClick={() => setActiveView('simulation')}
            className="btn btn-primary btn-sm"
            style={{ fontSize: '0.75rem', gap: '0.3rem' }}
          >
            <Play size={13} /> Run Live Demo <ArrowRight size={13} />
          </button>
        </div>
      </div>

      {/* Top 4 Operational Metric Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Sector Threat Index */}
        <div
          onClick={() => setActiveView('threat')}
          className="hud-card p-3 rounded-sm flex flex-col justify-between cursor-pointer hover:border-[#00e5ff]/50 transition-all"
        >
          <div className="flex items-center justify-between text-gray-400 text-[11px] font-mono-tech uppercase">
            <span>SECTOR RISK LEVEL</span>
            <Activity className="w-3.5 h-3.5 text-[#ff1744]" />
          </div>
          <div className="my-1 flex items-baseline gap-2">
            <span className="font-orbitron font-extrabold text-2xl text-white">
              {threat?.threat_score ?? 48}
            </span>
            <span className="text-[11px] font-display font-bold text-[#ff1744]">
              {threat?.threat_score && threat.threat_score >= 50 ? 'HIGH' : 'ELEVATED'}
            </span>
          </div>
          <div className="text-[10px] font-mono-tech text-gray-400 truncate">
            {threat?.active_breaches ?? 1} Zone Breach • {threat?.active_loiterers ?? 2} Loitering
          </div>
        </div>

        {/* Fleet Ingestion Status */}
        <div
          onClick={() => setActiveView('surveillance')}
          className="hud-card p-3 rounded-sm flex flex-col justify-between cursor-pointer hover:border-[#00e5ff]/50 transition-all"
        >
          <div className="flex items-center justify-between text-gray-400 text-[11px] font-mono-tech uppercase">
            <span>CCTV FEEDS ONLINE</span>
            <Server className="w-3.5 h-3.5 text-[#00e676]" />
          </div>
          <div className="my-1 flex items-baseline gap-2">
            <span className="font-orbitron font-extrabold text-2xl text-[#00e676]">
              {cameras.length}
            </span>
            <span className="text-[11px] font-mono-tech text-gray-400">ACTIVE CAMERAS</span>
          </div>
          <div className="text-[10px] font-mono-tech text-gray-400 truncate">
            100% Ingestion Coverage • 0 Hardware Swap
          </div>
        </div>

        {/* AI Processing Speed */}
        <div className="hud-card p-3 rounded-sm flex flex-col justify-between">
          <div className="flex items-center justify-between text-gray-400 text-[11px] font-mono-tech uppercase">
            <span>AI PROCESSING SPEED</span>
            <Zap className="w-3.5 h-3.5 text-[#00e5ff]" />
          </div>
          <div className="my-1 flex items-baseline gap-2">
            <span className="font-orbitron font-extrabold text-2xl text-white">
              {metrics?.ai_processing_fps.toFixed(1) ?? '31.2'}
            </span>
            <span className="text-[10px] font-mono-tech text-gray-400">FPS</span>
          </div>
          <div className="text-[10px] font-mono-tech text-gray-400 truncate">
            YOLOv8n + ByteTrack Kalman Inference
          </div>
        </div>

        {/* Tracked Centroids */}
        <div
          onClick={() => setActiveView('incidents')}
          className="hud-card p-3 rounded-sm flex flex-col justify-between cursor-pointer hover:border-[#00e5ff]/50 transition-all"
        >
          <div className="flex items-center justify-between text-gray-400 text-[11px] font-mono-tech uppercase">
            <span>TRACKED TARGETS</span>
            <Layers className="w-3.5 h-3.5 text-[#2979ff]" />
          </div>
          <div className="my-1 flex items-baseline gap-2">
            <span className="font-orbitron font-extrabold text-2xl text-white">
              {threat?.active_tracks ?? 5}
            </span>
            <span className="text-[11px] font-display text-[#38bdf8]">Active Tracks</span>
          </div>
          <div className="text-[10px] font-mono-tech text-gray-400 truncate">
            {alerts.length} Total Alerts Logged
          </div>
        </div>
      </div>

      {/* Main 2-Column Tactical Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-4">
        {/* Left Column (7 cols): 3D Spatial Sector Map */}
        <div className="lg:col-span-7 flex flex-col gap-4">
          <div className="h-[430px] w-full">
            <TacticalMap3D
              cameras={cameras}
              zones={zones}
              boundaries={[]}
              alerts={alerts}
              selectedCameraId={selectedCamId}
              onSelectCamera={(id) => setSelectedCamId(id)}
            />
          </div>
        </div>

        {/* Right Column (5 cols): Live Alerts Ticker */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          <div className="flex-1 min-h-[430px]">
            <AlertTicker limit={6} />
          </div>
        </div>
      </div>

      {/* Primary Video Feed Preview Strip */}
      {activeCamera && (
        <div className="glass-panel p-3">
          <div className="flex items-center justify-between mb-2">
            <div className="flex items-center gap-2">
              <Eye className="w-4 h-4 text-[#00e5ff]" />
              <span className="font-display font-bold text-sm text-white">
                PRIMARY SURVEILLANCE FEED: {activeCamera.name}
              </span>
            </div>
            <span className="text-[10px] font-mono-tech text-gray-400">
              ID: {activeCamera.camera_id} • LOCATION: {activeCamera.location_label}
            </span>
          </div>
          <CameraCard camera={activeCamera} onRefresh={refreshAll} />
        </div>
      )}
    </div>
  );
};
