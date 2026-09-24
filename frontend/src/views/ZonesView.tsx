import React, { useState } from "react";
import {
  DEMO_ZONES,
  DEMO_BOUNDARIES,
  getSeverityColor,
  type SecurityZone,
  type VirtualBoundary,
} from "../lib/demoData";
import {
  Layers,
  Plus,
  Trash2,
  Crosshair,
  MapPin,
  Clock,
  Eye,
  EyeOff,
  Shield,
} from "lucide-react";

/* ═══════════════════════════════════════════════════════════════════
   ZONE MAP VISUALIZATION
   ═══════════════════════════════════════════════════════════════════ */
const ZoneMap: React.FC<{
  zones: SecurityZone[];
  boundaries: VirtualBoundary[];
}> = ({ zones, boundaries }) => (
  <div className="aspect-square bg-[var(--void-black)] rounded border border-[var(--border-dim)] relative overflow-hidden">
    <div className="absolute inset-0 tactical-grid-bg opacity-25" />

    <svg className="absolute inset-0 w-full h-full" viewBox="0 0 500 500">
      {/* Zones */}
      {zones.map((zone) => {
        const color = getSeverityColor(zone.severity);
        const points = zone.polygon.map((p: number[]) => `${p[0] * 1.25},${p[1] * 1.25}`).join(" ");
        return (
          <g key={zone.zone_id}>
            <polygon
              points={points}
              fill={`${color}08`}
              stroke={color}
              strokeWidth="1.5"
              strokeDasharray={zone.is_active ? "none" : "6,4"}
              opacity={zone.is_active ? 0.8 : 0.4}
            />
            {zone.polygon.map((p: number[], i: number) => (
              <circle key={i} cx={p[0] * 1.25} cy={p[1] * 1.25} r="3" fill={color} stroke="#fff" strokeWidth="1" />
            ))}
            <text
              x={zone.polygon.reduce((sum: number, p: number[]) => sum + p[0], 0) / zone.polygon.length * 1.25}
              y={zone.polygon.reduce((sum: number, p: number[]) => sum + p[1], 0) / zone.polygon.length * 1.25}
              textAnchor="middle"
              fill={color}
              fontSize="9"
              fontFamily="'JetBrains Mono', monospace"
              opacity="0.7"
            >
              {zone.name.toUpperCase()}
            </text>
          </g>
        );
      })}

      {/* Tripwires */}
      {boundaries.map((b) => {
        const color = getSeverityColor(b.severity);
        return (
          <g key={b.boundary_id}>
            <line
              x1={b.pt1[0] * 1.25} y1={b.pt1[1] * 1.25}
              x2={b.pt2[0] * 1.25} y2={b.pt2[1] * 1.25}
              stroke={color} strokeWidth="2" strokeDasharray="10,5"
            />
            <circle cx={b.pt1[0] * 1.25} cy={b.pt1[1] * 1.25} r="4" fill={color} stroke="#fff" strokeWidth="1.5" />
            <circle cx={b.pt2[0] * 1.25} cy={b.pt2[1] * 1.25} r="4" fill={color} stroke="#fff" strokeWidth="1.5" />
            <text
              x={(b.pt1[0] + b.pt2[0]) / 2 * 1.25}
              y={(b.pt1[1] + b.pt2[1]) / 2 * 1.25 - 8}
              textAnchor="middle" fill={color} fontSize="8"
              fontFamily="'JetBrains Mono', monospace" opacity="0.6"
            >
              {b.name.toUpperCase()}
            </text>
          </g>
        );
      })}
    </svg>
  </div>
);

/* ═══════════════════════════════════════════════════════════════════
   ZONES VIEW
   ═══════════════════════════════════════════════════════════════════ */
export const ZonesView: React.FC = () => {
  const [zones, setZones] = useState(DEMO_ZONES);
  const [boundaries, setBoundaries] = useState(DEMO_BOUNDARIES);

  const toggleZone = (id: string) => {
    setZones((prev) => prev.map((z) => (z.zone_id === id ? { ...z, is_active: !z.is_active } : z)));
  };

  const toggleBoundary = (id: string) => {
    setBoundaries((prev) => prev.map((b) => (b.boundary_id === id ? { ...b, is_active: !b.is_active } : b)));
  };

  return (
    <div className="space-y-4 font-sans">
      <div className="flex items-center justify-between flex-wrap gap-3 pb-2 border-b border-[var(--border-dim)]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded border border-[rgba(0,229,255,0.3)] bg-[rgba(0,229,255,0.06)] flex items-center justify-center">
            <Layers className="w-4 h-4 text-[#00e5ff]" />
          </div>
          <div>
            <h2 className="font-condensed font-bold text-lg tracking-wide text-white uppercase">
              SECURITY ZONES & BOUNDARIES
            </h2>
            <p className="text-[10px] font-mono text-[#64748b]">
              RAY-CASTING CONTAINMENT · DWELL MONITORING · VIRTUAL TRIPWIRES
            </p>
          </div>
        </div>
        <button className="px-3 py-1.5 rounded bg-[#00e5ff] text-black font-mono font-bold text-xs flex items-center gap-1.5 hover:bg-[#38bdf8] transition-colors">
          <Plus className="w-3.5 h-3.5" /> CREATE ZONE
        </button>
      </div>

      <div className="grid grid-cols-12 gap-3">
        {/* Map */}
        <div className="col-span-12 lg:col-span-8">
          <ZoneMap zones={zones} boundaries={boundaries} />
        </div>

        {/* Zone list */}
        <div className="col-span-12 lg:col-span-4 space-y-3">
          {/* Zones */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">
                <Layers className="w-3.5 h-3.5 text-[var(--c2-cyan)]" /> POLYGON ZONES
              </span>
            </div>
            <div className="space-y-2">
              {zones.map((zone) => {
                const color = getSeverityColor(zone.severity);
                return (
                  <div
                    key={zone.zone_id}
                    className="p-2.5 rounded border border-[var(--border-dim)] bg-[var(--void-black)]"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
                        <span className="text-[11px] font-bold text-[var(--text-bright)]">{zone.name}</span>
                      </div>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => toggleZone(zone.zone_id)}
                          className="p-1 hover:bg-[rgba(255,255,255,0.05)] rounded"
                          title={zone.is_active ? "Disable zone" : "Enable zone"}
                        >
                          {zone.is_active ? (
                            <Eye className="w-3 h-3 text-[var(--c2-emerald)]" />
                          ) : (
                            <EyeOff className="w-3 h-3 text-[var(--text-dim)]" />
                          )}
                        </button>
                        <button className="p-1 hover:bg-[rgba(255,255,255,0.05)] rounded" title="Delete zone">
                          <Trash2 className="w-3 h-3 text-[var(--text-dim)] hover:text-[var(--c2-crimson)]" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-[9px] font-mono text-[var(--text-muted)]">
                      <span
                        className="px-1.5 py-0.5 rounded"
                        style={{ backgroundColor: `${color}10`, color }}
                      >
                        {zone.severity.toUpperCase()}
                      </span>
                      {zone.loitering_threshold_seconds && (
                        <span className="flex items-center gap-1">
                          <Clock className="w-2.5 h-2.5" /> {zone.loitering_threshold_seconds}s loiter
                        </span>
                      )}
                      <span>{zone.polygon.length} points</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Tripwires */}
          <div className="panel">
            <div className="panel-header">
              <span className="panel-title">
                <Crosshair className="w-3.5 h-3.5 text-[var(--c2-crimson)]" /> TRIPWIRES
              </span>
            </div>
            <div className="space-y-2">
              {boundaries.map((b) => {
                const color = getSeverityColor(b.severity);
                return (
                  <div
                    key={b.boundary_id}
                    className="p-2.5 rounded border border-[var(--border-dim)] bg-[var(--void-black)]"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-[11px] font-bold text-[var(--text-bright)]">{b.name}</span>
                      <div className="flex items-center gap-1">
                        <button
                          onClick={() => toggleBoundary(b.boundary_id)}
                          className="p-1 hover:bg-[rgba(255,255,255,0.05)] rounded"
                        >
                          {b.is_active ? (
                            <Eye className="w-3 h-3 text-[var(--c2-emerald)]" />
                          ) : (
                            <EyeOff className="w-3 h-3 text-[var(--text-dim)]" />
                          )}
                        </button>
                        <button className="p-1 hover:bg-[rgba(255,255,255,0.05)] rounded">
                          <Trash2 className="w-3 h-3 text-[var(--text-dim)] hover:text-[var(--c2-crimson)]" />
                        </button>
                      </div>
                    </div>
                    <div className="flex items-center gap-3 text-[9px] font-mono text-[var(--text-muted)]">
                      <span
                        className="px-1.5 py-0.5 rounded"
                        style={{ backgroundColor: `${color}10`, color }}
                      >
                        {b.severity.toUpperCase()}
                      </span>
                      <span>[{b.pt1[0]},{b.pt1[1]}] → [{b.pt2[0]},{b.pt2[1]}]</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
