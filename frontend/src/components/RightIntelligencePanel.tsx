import React, { useState } from "react";
import {
  ArrowRight,
  MoreHorizontal,
  ChevronRight,
} from "lucide-react";
import { DossierModal } from "./DossierModal";

interface RightIntelligencePanelProps {
  onViewEvidence?: () => void;
  onViewFullTrack?: () => void;
}

export const RightIntelligencePanel: React.FC<RightIntelligencePanelProps> = ({
  onViewEvidence,
  onViewFullTrack,
}) => {
  const [isDossierOpen, setIsDossierOpen] = useState(false);

  return (
    <aside className="w-full xl:w-[460px] flex flex-col gap-4 font-mono select-none">
      {/* ── Top Incident Header (Stitch Precision) ── */}
      <div className="flex items-center justify-between text-[11px] font-mono tracking-[0.2em] uppercase pb-1 border-b border-[#171e27]">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-white">ACTIVE INCIDENT</span>
          <span className="text-[#414d5d]">// 01</span>
        </div>
        <div className="flex items-center gap-1.5 text-[9.5px] text-[#ff6b6b] font-medium tracking-widest">
          <span className="w-1.5 h-1.5 rounded-none bg-[#ff6b6b] animate-pulse" />
          <span>HIGH PRIORITY</span>
        </div>
      </div>

      {/* ── Incident Details Card (Sharp 90-degree corners per Stitch DESIGN.md) ── */}
      <div className="p-4 rounded-none bg-[#0c1017]/90 border border-[#1b232f] backdrop-blur-md shadow-lg flex flex-col gap-4">
        {/* Upper Split: Frame Crop + Specs */}
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-3.5">
          {/* CCTV Frame Crop (Left 5 cols) */}
          <div className="sm:col-span-5 relative rounded-none overflow-hidden border border-[#ff6b6b]/40 bg-[#040608] aspect-4/3 flex items-center justify-center group">
            <img
              src="/assets/images/percepta_thermal_walking.jpg"
              alt="CCTV Evidence Source"
              className="w-full h-full object-cover filter contrast-125 brightness-90 grayscale group-hover:scale-105 transition-transform duration-500"
              onError={(e) => {
                (e.target as HTMLElement).style.display = "none";
              }}
            />

            {/* Target Bounding Box Overlay with Corner Ticks */}
            <div className="absolute inset-x-6 inset-y-4 border border-[#ff6b6b] bg-[#ff6b6b]/10 pointer-events-none">
              <span className="absolute -top-3 left-0 px-1 bg-[#ff6b6b] text-[7.5px] font-mono font-bold text-black uppercase">
                PERSON-042
              </span>
            </div>

            {/* Camera & Timestamp Watermark */}
            <div className="absolute bottom-1 left-1.5 right-1.5 flex items-center justify-between text-[8px] font-mono text-white/90 bg-black/85 px-1.5 py-0.5 rounded-none pointer-events-none">
              <span>CAM-04</span>
              <span>14:32:18</span>
            </div>
          </div>

          {/* Incident Specs (Right 7 cols) */}
          <div className="sm:col-span-7 flex flex-col justify-between">
            <div>
              <h3 className="font-display text-2xl tracking-[0.04em] uppercase text-white leading-none font-normal">
                RESTRICTED-ZONE ENTRY
              </h3>
              <div className="text-[11px] font-mono text-[#dcc495] font-semibold tracking-wider mt-1">
                PERSON-042
              </div>

              {/* Spec Rows */}
              <div className="mt-3 space-y-1 text-[10px] font-mono">
                <div className="flex items-center justify-between text-[#8492a6]">
                  <span className="tracking-wider">LOCATION</span>
                  <strong className="text-white font-normal">North Perimeter</strong>
                </div>
                <div className="flex items-center justify-between text-[#8492a6]">
                  <span className="tracking-wider">CAMERA</span>
                  <strong className="text-white font-normal">CAM-04</strong>
                </div>
                <div className="flex items-center justify-between text-[#8492a6]">
                  <span className="tracking-wider">TIME</span>
                  <strong className="text-white font-normal">14:32:18</strong>
                </div>
                <div className="flex items-center justify-between pt-1 border-t border-[#171e27]">
                  <span className="text-[#8492a6] tracking-wider">THREAT</span>
                  <div className="flex items-center gap-1.5">
                    <span className="font-bold text-white">72 / 100</span>
                    <span className="px-1.5 py-0.2 rounded-none bg-[#ff6b6b]/20 text-[#ff6b6b] font-bold text-[8.5px] border border-[#ff6b6b]/40">
                      HIGH
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Tactical Observations (Why) */}
        <div className="pt-2 border-t border-[#171e27] space-y-1 text-[10px] font-mono text-[#8492a6]">
          <div className="flex items-center gap-2">
            <span className="w-1 h-1 rounded-none bg-[#ff6b6b]" />
            <span>Restricted-zone persistence</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-1 h-1 rounded-none bg-[#38e8cb]" />
            <span>Movement direction: North-East</span>
          </div>
          <div className="flex items-center gap-2">
            <span className="w-1 h-1 rounded-none bg-[#dcc495]" />
            <span>Dwell time: 42s</span>
          </div>
        </div>

        {/* Action Buttons (Stitch Brutalist Action Triggers) */}
        <div className="flex items-center gap-2 pt-1">
          <button
            type="button"
            onClick={() => {
              setIsDossierOpen(true);
              onViewEvidence?.();
            }}
            className="flex-1 py-2.5 px-4 rounded-none border border-[#26534e] bg-[#0d1c1a]/40 hover:bg-[#122824] hover:border-[#38e8cb] text-neutral-200 text-xs font-mono tracking-[0.2em] uppercase font-semibold transition-all flex items-center justify-center gap-2 cursor-pointer group"
          >
            <span>VIEW EVIDENCE</span>
            <ArrowRight size={13} className="text-[#38e8cb] group-hover:translate-x-1 transition-transform" />
          </button>

          <button
            type="button"
            onClick={() => setIsDossierOpen(true)}
            className="p-2.5 rounded-none border border-[#1b232f] bg-[#0c1017]/70 hover:bg-[#121720] hover:border-[#273445] text-[#8492a6] hover:text-white transition-colors cursor-pointer"
            title="Additional Target Actions"
          >
            <MoreHorizontal size={14} />
          </button>
        </div>
      </div>

      {/* ── Entity Track Section (Follow Track Stepper) ── */}
      <div className="p-4 rounded-none bg-[#0c1017]/90 border border-[#1b232f] backdrop-blur-md shadow-lg flex flex-col gap-3.5">
        {/* Track Header */}
        <div className="flex items-center justify-between text-[11px] font-mono tracking-[0.2em] uppercase">
          <div className="flex items-center gap-2 text-[#8492a6]">
            <span>ENTITY TRACK</span>
            <span className="text-[#414d5d]">//</span>
            <span className="text-white font-semibold">PERSON-042</span>
          </div>
          <div className="text-[10px] text-[#38e8cb] font-semibold tracking-widest">
            CONFIDENCE 87%
          </div>
        </div>

        {/* Sequential Camera Timeline Stepper */}
        <div className="py-2.5 flex items-center justify-between gap-1 text-[9.5px] font-mono">
          {/* CAM-01 */}
          <div className="flex flex-col items-center text-center">
            <div className="flex items-center gap-1.5 text-[#38e8cb]">
              <span className="w-1.5 h-1.5 rounded-none bg-[#38e8cb]" />
              <span className="font-semibold">CAM-01</span>
            </div>
            <span className="text-[8.5px] text-[#5e7083] mt-1">14:31:02</span>
          </div>

          <div className="flex-1 h-px bg-[#38e8cb]/30 relative mx-1">
            <ChevronRight size={12} className="absolute -top-1.5 left-1/2 -translate-x-1/2 text-[#38e8cb]/60" />
          </div>

          {/* CAM-02 */}
          <div className="flex flex-col items-center text-center">
            <div className="flex items-center gap-1.5 text-[#38e8cb]">
              <span className="w-1.5 h-1.5 rounded-none bg-[#38e8cb]" />
              <span className="font-semibold">CAM-02</span>
            </div>
            <span className="text-[8.5px] text-[#5e7083] mt-1">14:31:46</span>
          </div>

          <div className="flex-1 h-px bg-[#ff6b6b]/40 relative mx-1">
            <ChevronRight size={12} className="absolute -top-1.5 left-1/2 -translate-x-1/2 text-[#ff6b6b]/70" />
          </div>

          {/* CAM-04 */}
          <div className="flex flex-col items-center text-center">
            <div className="flex items-center gap-1.5 text-[#ff6b6b]">
              <span className="w-1.5 h-1.5 rounded-none bg-[#ff6b6b] animate-pulse" />
              <span className="font-semibold">CAM-04</span>
            </div>
            <span className="text-[8.5px] text-[#ff6b6b] mt-1 font-semibold">14:32:18</span>
          </div>
        </div>

        {/* View Full Track Button */}
        <button
          type="button"
          onClick={() => {
            setIsDossierOpen(true);
            onViewFullTrack?.();
          }}
          className="w-full py-2.5 px-4 rounded-none border border-[#1b232f] bg-[#0c1017]/70 hover:bg-[#121720] hover:border-[#38e8cb] text-[#abb7c5] hover:text-white text-xs font-mono tracking-[0.2em] uppercase font-semibold transition-all flex items-center justify-center gap-2 cursor-pointer group"
        >
          <span>VIEW FULL TRACK</span>
          <ArrowRight size={13} className="text-[#38e8cb] group-hover:translate-x-1 transition-transform" />
        </button>
      </div>

      {/* Dossier Modal when inspecting target evidence */}
      {isDossierOpen && (
        <DossierModal
          dossier={{
            incident_id: "INC-RESTRICTED-ZONE",
            timestamp: "2026-09-11T14:32:18Z",
            camera_id: "CAM-04",
            zone_name: "North Perimeter Restricted Zone",
            severity: "CRITICAL",
            summary: "Restricted-zone persistence and boundary breach detected by CAM-04",
            evidence_path: "/assets/images/percepta_thermal_walking.jpg",
            chain_of_custody_hash: "0x8f7e2a9b3c4d5e6f1a2b3c4d5e6f7a8b9c0d1e2f",
            verification_status: "VERIFIED",
          } as any}
          onClose={() => setIsDossierOpen(false)}
        />
      )}
    </aside>
  );
};
