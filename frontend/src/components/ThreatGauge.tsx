import type { ThreatAssessment } from '../types/surveillance';
import { ShieldAlert, CheckCircle2 } from 'lucide-react';

interface ThreatGaugeProps {
  threat: ThreatAssessment | null;
}

export const ThreatGauge: React.FC<ThreatGaugeProps> = ({ threat }) => {
  const score = threat?.threat_score ?? 0;
  const level = threat?.threat_level ?? 'DEFCON_GREEN';

  // SVG Gauge Calculations
  const radius = 62;
  const circumference = 2 * Math.PI * radius;
  const strokeDashoffset = circumference - (score / 100) * circumference * 0.75; // 270 degree arc

  const getDefconMeta = () => {
    switch (level) {
      case 'DEFCON_RED':
        return {
          color: '#ff1744',
          label: 'DEFCON 1 — CRITICAL',
          sub: 'MAXIMUM SECURITY BREACH',
          bg: 'rgba(255, 23, 68, 0.12)',
          border: 'rgba(255, 23, 68, 0.4)',
        };
      case 'DEFCON_ORANGE':
        return {
          color: '#ff6d00',
          label: 'DEFCON 2 — ELEVATED',
          sub: 'IMMINENT PERIMETER INTRUSION',
          bg: 'rgba(255, 109, 0, 0.12)',
          border: 'rgba(255, 109, 0, 0.4)',
        };
      case 'DEFCON_YELLOW':
        return {
          color: '#ffab00',
          label: 'DEFCON 3 — WARNING',
          sub: 'SUSPICIOUS DWELLING DETECTED',
          bg: 'rgba(255, 171, 0, 0.12)',
          border: 'rgba(255, 171, 0, 0.4)',
        };
      default:
        return {
          color: '#00e676',
          label: 'DEFCON 4 — NORMAL',
          sub: 'SECTOR PERIMETER SECURE',
          bg: 'rgba(0, 230, 118, 0.12)',
          border: 'rgba(0, 230, 118, 0.4)',
        };
    }
  };

  const meta = getDefconMeta();

  return (
    <div className="glass-panel p-4 flex flex-col justify-between h-full">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-white/10 pb-2.5">
        <div className="flex items-center gap-2">
          <ShieldAlert className="w-4 h-4" style={{ color: meta.color }} />
          <span className="font-display font-bold text-sm tracking-wider text-white">THREAT LEVEL ASSESSMENT</span>
        </div>
        <div
          className="px-2 py-0.5 text-[10px] font-mono-tech font-bold rounded"
          style={{ backgroundColor: meta.bg, color: meta.color, border: `1px solid ${meta.border}` }}
        >
          {meta.label}
        </div>
      </div>

      {/* Radial Dial & Score */}
      <div className="flex items-center justify-center my-3 relative">
        <svg className="w-40 h-40 transform -rotate-135" viewBox="0 0 160 160">
          {/* Background Track */}
          <circle
            cx="80"
            cy="80"
            r={radius}
            fill="transparent"
            stroke="rgba(255, 255, 255, 0.08)"
            strokeWidth="10"
            strokeDasharray={`${circumference * 0.75} ${circumference * 0.25}`}
            strokeLinecap="round"
          />
          {/* Active Fill */}
          <circle
            cx="80"
            cy="80"
            r={radius}
            fill="transparent"
            stroke={meta.color}
            strokeWidth="10"
            strokeDasharray={circumference}
            strokeDashoffset={strokeDashoffset}
            strokeLinecap="round"
            className="transition-all duration-700 ease-out"
          />
        </svg>

        {/* Center Score Display */}
        <div className="absolute flex flex-col items-center justify-center text-center">
          <span className="font-orbitron font-extrabold text-3xl tracking-tight text-white">{score}</span>
          <span className="text-[10px] font-mono-tech text-gray-400 uppercase tracking-widest">THREAT INDEX</span>
          <span className="text-[9px] font-display font-semibold mt-0.5" style={{ color: meta.color }}>
            {meta.sub}
          </span>
        </div>
      </div>

      {/* Contributing Factors Matrix */}
      <div className="space-y-2 text-xs">
        <div className="flex items-center justify-between text-gray-400 font-mono-tech text-[11px]">
          <span>CONTRIBUTING FACTORS</span>
          <span className="text-[10px] text-gray-500">IMPACT</span>
        </div>

        {threat?.contributing_factors && threat.contributing_factors.length > 0 ? (
          threat.contributing_factors.slice(0, 3).map((factor, idx) => (
            <div key={idx} className="flex items-center justify-between p-1.5 bg-black/40 border border-white/5 rounded text-[11px] font-mono-tech">
              <span className="text-gray-300 truncate max-w-[190px]">{factor}</span>
              <span className="text-red-400 font-bold">+{(idx + 1) * 15}</span>
            </div>
          ))
        ) : (
          <div className="flex items-center gap-2 p-2 bg-emerald-950/20 border border-emerald-500/20 rounded text-[11px] font-mono-tech text-emerald-400">
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Perimeter integrity nominal</span>
          </div>
        )}
      </div>

      {/* Recommended Tactical SOP */}
      {threat?.recommended_action && (
        <div className="mt-3 pt-2.5 border-t border-white/10">
          <div className="text-[10px] font-mono-tech text-gray-400 mb-1">RECOMMENDED OPERATIONAL SOP:</div>
          <div className="text-[11px] font-display font-semibold text-[#00e5ff] bg-[#00e5ff]/10 p-2 border border-[#00e5ff]/30 rounded">
            {threat.recommended_action}
          </div>
        </div>
      )}
    </div>
  );
};
