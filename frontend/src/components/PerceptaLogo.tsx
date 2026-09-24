import React from "react";

interface LogoProps {
  className?: string;
  size?: number;
  showText?: boolean;
}

export const PerceptaLogo: React.FC<LogoProps> = ({
  className = "",
  size = 28,
  showText = true,
}) => {
  return (
    <div className={`flex items-center gap-3 select-none group ${className}`}>
      {/* Precision Tactical Aperture SVG Emblem */}
      <div
        className="relative flex items-center justify-center shrink-0"
        style={{ width: size, height: size }}
      >
        <svg
          viewBox="0 0 36 36"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full transition-transform duration-500 group-hover:rotate-45"
        >
          {/* Hexagonal Tactical Hull */}
          <polygon
            points="18,2 32,10 32,26 18,34 4,26 4,10"
            stroke="#9ee7df"
            strokeWidth="1.2"
            strokeOpacity="0.45"
            className="transition-all duration-300 group-hover:stroke-opacity-90"
          />

          {/* Corner Notch Accents */}
          <line x1="18" y1="2" x2="18" y2="7" stroke="#9ee7df" strokeWidth="1.5" />
          <line x1="18" y1="29" x2="18" y2="34" stroke="#9ee7df" strokeWidth="1.5" />
          <line x1="4" y1="18" x2="9" y2="18" stroke="#9ee7df" strokeWidth="1.5" />
          <line x1="27" y1="18" x2="32" y2="18" stroke="#9ee7df" strokeWidth="1.5" />

          {/* Concentric Radar Ring */}
          <circle
            cx="18"
            cy="18"
            r="8"
            stroke="#9ee7df"
            strokeWidth="0.9"
            strokeDasharray="2.5 2"
            strokeOpacity="0.6"
          />

          {/* Core Sensor / Signal Dot */}
          <circle
            cx="18"
            cy="18"
            r="2.5"
            fill="#9ee7df"
            className="shadow-[0_0_10px_#9ee7df]"
          />
        </svg>

        {/* Ambient Pulse Glow */}
        <div
          className="absolute inset-0 rounded-full bg-[#9ee7df]/10 blur-sm pointer-events-none group-hover:bg-[#9ee7df]/25 transition-all"
        />
      </div>

      {showText && (
        <div className="flex flex-col leading-none">
          <div className="flex items-center gap-1.5">
            <span className="font-['Barlow_Condensed',sans-serif] font-bold text-lg tracking-[0.22em] text-[#e8ebe6] uppercase transition-colors group-hover:text-white">
              PERCEPTA
            </span>
            <span className="w-1.5 h-1.5 rounded-full bg-[#9ee7df] shadow-[0_0_6px_#9ee7df] animate-pulse" />
          </div>
          <span className="font-mono text-[8px] tracking-[0.32em] text-[#869099] uppercase mt-0.5">
            DEFENSE OS
          </span>
        </div>
      )}
    </div>
  );
};
