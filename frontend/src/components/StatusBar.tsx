import React from "react";
import { Plus } from "lucide-react";

interface StatusBarProps {
  onRegisterFeed?: () => void;
  cameraCount?: number;
  alertCount?: number;
  threatLevel?: string;
}

export const StatusBar: React.FC<StatusBarProps> = ({ onRegisterFeed }) => {
  return (
    <footer className="h-9 border-t border-tactical-border bg-[#070a0f] px-4 flex items-center justify-between z-30 shrink-0 font-mono text-[9.5px] select-none whitespace-nowrap overflow-hidden">
      {/* ── Monospace Security Telemetry Stream with exact Auth strings ── */}
      <div className="flex items-center space-x-3 text-tactical-slateText overflow-hidden text-ellipsis whitespace-nowrap">
        <span className="text-tactical-sand font-semibold">
          SYS.ID // <span className="text-white">PRCPTA-SEC-C2</span>
        </span>
        <span className="text-tactical-borderLight">|</span>
        <span>
          HARDWARE MODULE: <strong className="text-slate-200">FIPS 140-3</strong>
        </span>
        <span className="text-tactical-borderLight">|</span>
        <span>
          ENTROPY: <strong className="text-tactical-mint">99.9% [OPTIMAL]</strong>
        </span>
        <span className="text-tactical-borderLight hidden xl:inline">|</span>
        <span className="hidden xl:inline text-tactical-slateMuted">
          STRICT ACCESS LOGGING IN EFFECT • INGRESS: 188.51.100.32 [VALIDATED]
        </span>
        <span className="text-tactical-borderLight">|</span>
        <span>
          WAL: <strong className="text-tactical-mint">SYNCED [14ms]</strong>
        </span>
        <span className="text-tactical-borderLight">|</span>
        <span>
          HASH: <span className="text-tactical-slateText font-medium">sha256:d8a9...f2ce</span>
        </span>
      </div>

      {/* ── Rapid Command Action Buttons matching Auth Button Style ── */}
      <div className="flex items-center space-x-2 shrink-0">
        <button
          type="button"
          onClick={onRegisterFeed}
          className="px-3 py-1 rounded bg-tactical-mint hover:bg-tactical-mintBright text-black font-bold text-[9px] uppercase tracking-wider transition-all flex items-center space-x-1 shadow-[0_0_12px_rgba(16,229,153,0.35)] cursor-pointer active:scale-95"
        >
          <span>+ REGISTER FEED</span>
        </button>
      </div>
    </footer>
  );
};

