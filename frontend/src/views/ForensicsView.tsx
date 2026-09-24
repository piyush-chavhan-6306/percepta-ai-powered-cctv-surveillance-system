import React, { useState } from "react";
import {
  CheckCircle2,
  FileCheck,
  Shield,
  Download,
  Search,
  Hash,
  Clock,
  Target,
  Eye,
  Camera,
  Layers,
  FileText,
  AlertTriangle,
} from "lucide-react";

const DEMO_HASH_CHAIN = [
  { block: 1, hash: "a3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2c", prev: "0000000000000000000000000000000000000000000000000000000000000000", verified: true, timestamp: new Date(Date.now() - 3600000).toISOString(), eventCount: 24 },
  { block: 2, hash: "7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3", prev: "a3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2c", verified: true, timestamp: new Date(Date.now() - 2400000).toISOString(), eventCount: 31 },
  { block: 3, hash: "b9c4d72e6ae1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8", prev: "7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3", verified: true, timestamp: new Date(Date.now() - 1200000).toISOString(), eventCount: 28 },
  { block: 4, hash: "e1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8c2e91b7d2", prev: "b9c4d72e6ae1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8", verified: true, timestamp: new Date(Date.now() - 600000).toISOString(), eventCount: 35 },
  { block: 5, hash: "c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e", prev: "e1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8c2e91b7d2", verified: true, timestamp: new Date(Date.now() - 120000).toISOString(), eventCount: 22 },
];

const DEMO_AUDIT = {
  totalChecked: 14382,
  authentic: 14382,
  tampered: 0,
  verdict: "PASS_INTEGRITY_VERIFIED" as const,
};

import { api } from "@/api/client";
import type { EvidenceVerificationResult } from "@/types/surveillance";

export const ForensicsView: React.FC = () => {
  const [verifyId, setVerifyId] = useState("");
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<EvidenceVerificationResult | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);
  const [activeEvidenceTab, setActiveEvidenceTab] = useState<"target" | "anpr" | "face" | "weapon">("target");

  const handleVerify = async () => {
    if (!verifyId.trim()) return;
    setVerifying(true);
    setVerifyResult(null);
    setVerifyError(null);
    try {
      const res = await api.verifyEvidenceRecord(verifyId.trim());
      setVerifyResult(res);
    } catch (err: any) {
      setVerifyError(err.message || "Failed to verify evidence");
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="space-y-4 font-sans">
      {/* View Header */}
      <div className="flex items-center justify-between flex-wrap gap-3 pb-2 border-b border-[var(--border-dim)]">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded border border-[rgba(0,230,118,0.3)] bg-[rgba(0,230,118,0.06)] flex items-center justify-center">
            <FileCheck className="w-4 h-4 text-[#00e676]" />
          </div>
          <div>
            <h2 className="font-condensed font-bold text-lg tracking-wide text-white uppercase">
              EVIDENCE VAULT & FORENSIC AUDIT
            </h2>
            <p className="text-[10px] font-mono text-[#64748b]">
              TARGET-SPECIFIC CROPS · SHA-256 TAMPER AUDIT · COURT-ADMISSIBLE CHAIN
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button className="px-3 py-1.5 rounded border border-[rgba(255,255,255,0.1)] bg-[rgba(8,13,22,0.8)] text-xs font-mono text-[#94a3b8] hover:text-white flex items-center gap-1.5 transition-colors">
            <Download className="w-3 h-3" /> EXPORT JSON
          </button>
          <button className="px-3 py-1.5 rounded border border-[rgba(255,255,255,0.1)] bg-[rgba(8,13,22,0.8)] text-xs font-mono text-[#94a3b8] hover:text-white flex items-center gap-1.5 transition-colors">
            <Download className="w-3 h-3" /> EXPORT CSV
          </button>
        </div>
      </div>

      {/* ── 1. Target-Specific Forensic Evidence Inspector (Screenshot 4) ─── */}
      <div className="rounded border border-[rgba(0,229,255,0.25)] bg-[rgba(8,13,22,0.95)] p-4 shadow-xl">
        <div className="flex items-center justify-between flex-wrap gap-3 border-b border-[rgba(255,255,255,0.06)] pb-3 mb-4">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-[#00e5ff]" />
            <span className="font-condensed font-bold text-sm tracking-wider text-white uppercase">
              TARGET-SPECIFIC EVIDENCE INSPECTOR
            </span>
          </div>
          <div className="flex items-center gap-1 bg-[rgba(5,7,10,0.8)] p-1 rounded border border-[rgba(255,255,255,0.06)] font-mono text-[10px]">
            {[
              { id: "target" as const, label: "TARGET CROP" },
              { id: "anpr" as const, label: "ANPR / PLATE" },
              { id: "face" as const, label: "FACE OBS." },
              { id: "weapon" as const, label: "WEAPON OBS." },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveEvidenceTab(tab.id)}
                className={`px-3 py-1 rounded transition-all font-bold ${
                  activeEvidenceTab === tab.id
                    ? "bg-[#00e5ff] text-black shadow-[0_0_8px_#00e5ff]"
                    : "text-[#64748b] hover:text-white"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Evidence Content Split */}
        <div className="grid grid-cols-12 gap-4 items-center">
          {/* Visual Crop Box (Screenshot 4 Reference) */}
          <div className="col-span-12 lg:col-span-6">
            <div className="aspect-[16/9] rounded border border-[rgba(0,229,255,0.3)] bg-[#05070a] relative overflow-hidden flex flex-col justify-between p-4 shadow-inner">
              <div className="flex items-center justify-between font-mono text-[10px] text-[#00e5ff] z-10">
                <span>EVIDENCE / TARGET CROP</span>
                <span>FRAME 14:32:18</span>
              </div>

              {/* Centered Target Highlight */}
              <div className="self-center my-auto w-32 h-44 border-2 border-[#00e5ff] rounded relative flex items-end justify-center pb-1.5 shadow-[0_0_20px_rgba(0,229,255,0.2)]">
                <div className="absolute top-1 right-1 px-1 py-0.5 bg-[#00e5ff] text-black font-mono text-[8px] font-bold">
                  94.2%
                </div>
                <div className="font-mono text-[9px] text-[#00e5ff] tracking-wider uppercase font-bold">
                  {activeEvidenceTab === "anpr" ? "PLATE CROP" : activeEvidenceTab === "face" ? "FACE CROP" : "TARGET CROP"}
                </div>
              </div>

              <div className="font-mono text-[10px] text-[#94a3b8] flex items-center justify-between z-10 border-t border-[rgba(255,255,255,0.06)] pt-2">
                <span className="text-white font-bold">PERSON-042</span>
                <span className="text-[#00e5ff]">CAM-01 · SOURCE FRAME</span>
                <span className="text-[#c4a882]">REASON: RESTRICTED ZONE ENTRY</span>
              </div>
            </div>
          </div>

          {/* Technical Metadata Ledger */}
          <div className="col-span-12 lg:col-span-6 space-y-2.5 font-mono text-xs">
            <div className="p-3 rounded border border-[rgba(255,255,255,0.06)] bg-[rgba(5,7,10,0.8)] space-y-2">
              <div className="flex justify-between border-b border-[rgba(255,255,255,0.04)] pb-1.5 text-[11px]">
                <span className="text-[#64748b]">PRIMARY ENTITY ID:</span>
                <span className="text-[#00e5ff] font-bold">GLOBAL-PERSON-042</span>
              </div>
              <div className="flex justify-between border-b border-[rgba(255,255,255,0.04)] pb-1.5 text-[11px]">
                <span className="text-[#64748b]">ASSOCIATED INCIDENT:</span>
                <span className="text-white font-bold">INC-2026-0042</span>
              </div>
              <div className="flex justify-between border-b border-[rgba(255,255,255,0.04)] pb-1.5 text-[11px]">
                <span className="text-[#64748b]">SOURCE CAMERA:</span>
                <span className="text-white">CAM-01 (NORTH GATE SENTINEL)</span>
              </div>
              <div className="flex justify-between border-b border-[rgba(255,255,255,0.04)] pb-1.5 text-[11px]">
                <span className="text-[#64748b]">TIMESTAMP (UTC):</span>
                <span className="text-[#cbd5e1]">2026-09-11 14:32:18.412</span>
              </div>
              <div className="flex justify-between border-b border-[rgba(255,255,255,0.04)] pb-1.5 text-[11px]">
                <span className="text-[#64748b]">TRIGGER REASON:</span>
                <span className="text-[#c4a882] font-bold">RESTRICTED ZONE ENTRY + DWELL</span>
              </div>
              <div className="flex justify-between text-[11px]">
                <span className="text-[#64748b]">SHA-256 HASH:</span>
                <span className="text-[#00e676] text-[10px] break-all">a3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2c</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── 2. SHA-256 Hash Chain & Integrity Audit ──────────────────────── */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left: Hash Chain Timeline */}
        <div className="col-span-12 lg:col-span-7 space-y-3">
          <div className="rounded border border-[rgba(255,255,255,0.08)] bg-[rgba(8,13,22,0.95)] p-4 shadow-lg">
            <div className="flex items-center justify-between border-b border-[rgba(255,255,255,0.06)] pb-3 mb-3">
              <div className="flex items-center gap-2">
                <Hash className="w-4 h-4 text-[#00e5ff]" />
                <span className="font-condensed font-bold text-sm tracking-wider text-white uppercase">
                  SHA-256 FORENSIC HASH CHAIN
                </span>
              </div>
              <span className="px-2 py-0.5 rounded bg-[rgba(0,230,118,0.1)] text-[#00e676] text-[9px] font-mono font-bold border border-[#00e67633]">
                CHAIN INTACT (0 TAMPERED)
              </span>
            </div>

            <div className="space-y-3 font-mono">
              {DEMO_HASH_CHAIN.map((block) => (
                <div
                  key={block.block}
                  className="p-3 rounded border border-[rgba(255,255,255,0.05)] bg-[rgba(5,7,10,0.8)] text-xs space-y-1"
                >
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="text-[#00e5ff] font-bold">BLOCK #{block.block}</span>
                    <span className="text-[#00e676] font-bold flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> VERIFIED
                    </span>
                  </div>
                  <div className="text-[10px] text-[#64748b] truncate">
                    HASH: <span className="text-[#cbd5e1]">{block.hash}</span>
                  </div>
                  <div className="flex items-center justify-between text-[9px] text-[#475569] pt-1">
                    <span>{new Date(block.timestamp).toLocaleTimeString()} UTC</span>
                    <span>{block.eventCount} EVENTS NORMALIZED</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Verification Form */}
        <div className="col-span-12 lg:col-span-5 space-y-3 font-mono">
          <div className="rounded border border-[rgba(255,255,255,0.08)] bg-[rgba(8,13,22,0.95)] p-4 shadow-lg">
            <div className="flex items-center gap-2 text-sm text-white font-condensed font-bold tracking-wider uppercase border-b border-[rgba(255,255,255,0.06)] pb-2 mb-3">
              <Search className="w-4 h-4 text-[#00e5ff]" /> VERIFY SPECIFIC EVENT HASH
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[10px] text-[#64748b] mb-1">EVENT / INCIDENT ID</label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={verifyId}
                    onChange={(e) => setVerifyId(e.target.value)}
                    placeholder="INC-2026-0042"
                    className="flex-1 bg-[rgba(5,7,10,0.8)] border border-[rgba(255,255,255,0.1)] rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#00e5ff]"
                  />
                  <button
                    onClick={handleVerify}
                    disabled={verifying || !verifyId}
                    className="px-4 py-1.5 bg-[#00e5ff] text-black text-xs font-bold rounded hover:bg-[#38bdf8] transition-colors disabled:opacity-40"
                  >
                    {verifying ? "CHECKING..." : "VERIFY"}
                  </button>
                </div>
              </div>

              {verifyError && (
                <div className="p-3 rounded border border-[rgba(239,68,68,0.3)] bg-[rgba(239,68,68,0.08)] text-xs text-[#ef4444] space-y-1">
                  <div className="flex items-center gap-1.5 font-bold">
                    <AlertTriangle className="w-3.5 h-3.5" /> VERIFICATION FAILED
                  </div>
                  <p className="text-[10px] text-[#fca5a5] font-mono break-all">{verifyError}</p>
                </div>
              )}

              {verifyResult && (
                <div
                  className={`p-3 rounded border text-xs space-y-2 font-mono ${
                    verifyResult.verification_status === "VERIFIED"
                      ? "border-[rgba(0,230,118,0.3)] bg-[rgba(0,230,118,0.06)] text-[#00e676]"
                      : verifyResult.verification_status === "COMPROMISED"
                      ? "border-[rgba(239,68,68,0.4)] bg-[rgba(239,68,68,0.1)] text-[#ef4444]"
                      : "border-[rgba(245,158,11,0.3)] bg-[rgba(245,158,11,0.08)] text-[#f59e0b]"
                  }`}
                >
                  <div className="flex items-center justify-between font-bold">
                    <span className="flex items-center gap-1.5">
                      {verifyResult.verification_status === "VERIFIED" ? (
                        <CheckCircle2 className="w-3.5 h-3.5" />
                      ) : (
                        <AlertTriangle className="w-3.5 h-3.5" />
                      )}
                      STATUS: {verifyResult.verification_status}
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-black/40 border border-white/10 text-white">
                      {verifyResult.evidence_type.toUpperCase()}
                    </span>
                  </div>

                  <p className="text-[10px] text-[#cbd5e1]">{verifyResult.audit_verdict}</p>

                  <div className="space-y-1 text-[9px] pt-1 border-t border-white/10 text-[#94a3b8]">
                    {verifyResult.stored_hash && (
                      <div className="break-all">
                        <span className="text-white font-semibold">STORED HASH: </span>
                        <span>{verifyResult.stored_hash}</span>
                      </div>
                    )}
                    {verifyResult.computed_hash && (
                      <div className="break-all">
                        <span className="text-white font-semibold">COMPUTED: </span>
                        <span className={verifyResult.verification_status === "VERIFIED" ? "text-[#00e676]" : "text-[#ef4444]"}>
                          {verifyResult.computed_hash}
                        </span>
                      </div>
                    )}
                    {verifyResult.file_path && (
                      <div className="truncate text-[#64748b]">
                        FILE: {verifyResult.file_path} ({verifyResult.file_bytes_checked} bytes)
                      </div>
                    )}
                    <div className="text-[8px] text-[#475569]">
                      VERIFIED AT: {new Date(verifyResult.verified_at).toLocaleTimeString()} UTC
                    </div>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
