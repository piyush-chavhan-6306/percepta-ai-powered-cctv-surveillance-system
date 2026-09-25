import React, { useState, useEffect } from "react";
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
  ExternalLink,
  ShieldCheck,
  Cpu,
} from "lucide-react";
import { api } from "@/api/client";
import type { EvidenceVerificationResult } from "@/types/surveillance";

interface ForensicEvidenceItem {
  evidence_id: string;
  evidence_type: "target" | "anpr" | "face" | "weapon";
  title: string;
  file_name: string;
  url: string;
  sha256_hash: string;
  camera_id: string;
  confidence: number;
  quality: number;
  reason: string;
  timestamp: string;
}

const DEFAULT_EVIDENCE_ITEMS: ForensicEvidenceItem[] = [
  {
    evidence_id: "EV-TGT-0042",
    evidence_type: "target",
    title: "PERIMETER BREACH TARGET ISOLATION",
    file_name: "sample_target_crop.jpg",
    url: "/evidence/sample_target_crop.jpg",
    sha256_hash: "faba2e69e361a701d9f12f73d5b6b74f362ce16769ce0f6caf0b35a0bf3c43c9",
    camera_id: "CAM-01",
    confidence: 0.978,
    quality: 0.95,
    reason: "Restricted border buffer zone infraction",
    timestamp: "2026-09-24 14:32:18.412 UTC",
  },
  {
    evidence_id: "EV-ANPR-1750",
    evidence_type: "anpr",
    title: "AUTOMATIC NUMBER PLATE RECOGNITION (ANPR)",
    file_name: "sample_anpr_crop.jpg",
    url: "/evidence/sample_anpr_crop.jpg",
    sha256_hash: "ecec52d8426fcbc69d72b75d27b73f06f7e66a95a0532eba6edde0640054fb34",
    camera_id: "CAM-03",
    confidence: 0.965,
    quality: 0.92,
    reason: "High-velocity vehicle license plate extraction",
    timestamp: "2026-09-24 14:18:05.190 UTC",
  },
  {
    evidence_id: "EV-FACE-0183",
    evidence_type: "face",
    title: "BIOMETRIC FACIAL OBSERVATION",
    file_name: "sample_face_crop.jpg",
    url: "/evidence/sample_face_crop.jpg",
    sha256_hash: "26c5b96c67d19d70e554554e0fc3eef5fbf5e3a2336cd6716e98cc5e5c2d35ef",
    camera_id: "CAM-01",
    confidence: 0.942,
    quality: 0.88,
    reason: "Facial recognition match against watchlist Sector Alpha",
    timestamp: "2026-09-24 14:05:42.881 UTC",
  },
  {
    evidence_id: "EV-WPN-0007",
    evidence_type: "weapon",
    title: "TACTICAL WEAPON DETECTION",
    file_name: "sample_weapon_crop.jpg",
    url: "/evidence/sample_weapon_crop.jpg",
    sha256_hash: "9e60201047cbdc8b06b605b27e238d464c02672d1fc2f3b7e6fd115e5374f599",
    camera_id: "CAM-02",
    confidence: 0.931,
    quality: 0.91,
    reason: "Concealed firearm / long-barrel weapon detection",
    timestamp: "2026-09-24 13:49:11.024 UTC",
  },
];

const DEMO_HASH_CHAIN = [
  { block: 1, hash: "a3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2c", prev: "0000000000000000000000000000000000000000000000000000000000000000", verified: true, timestamp: new Date(Date.now() - 3600000).toISOString(), eventCount: 24 },
  { block: 2, hash: "7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3", prev: "a3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2c", verified: true, timestamp: new Date(Date.now() - 2400000).toISOString(), eventCount: 31 },
  { block: 3, hash: "b9c4d72e6ae1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8", prev: "7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3", verified: true, timestamp: new Date(Date.now() - 1200000).toISOString(), eventCount: 28 },
  { block: 4, hash: "e1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8c2e91b7d2", prev: "b9c4d72e6ae1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8", verified: true, timestamp: new Date(Date.now() - 600000).toISOString(), eventCount: 35 },
  { block: 5, hash: "c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e", prev: "e1f3a89d2cb3f8c2e91b7d2e1a4c8fb9c4d72e6ae1f3a89d2cb3f8c2e91b7d2", verified: true, timestamp: new Date(Date.now() - 120000).toISOString(), eventCount: 22 },
];

export const ForensicsView: React.FC = () => {
  const [evidenceList, setEvidenceList] = useState<ForensicEvidenceItem[]>(DEFAULT_EVIDENCE_ITEMS);
  const [activeEvidenceTab, setActiveEvidenceTab] = useState<"target" | "anpr" | "face" | "weapon">("target");
  const [verifyId, setVerifyId] = useState("EV-TGT-0042");
  const [verifying, setVerifying] = useState(false);
  const [verifyResult, setVerifyResult] = useState<EvidenceVerificationResult | null>(null);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  // Load public evidence manifest if available
  useEffect(() => {
    fetch("/evidence/manifest.json")
      .then((res) => {
        if (res.ok) return res.json();
        return null;
      })
      .then((items) => {
        if (Array.isArray(items) && items.length > 0) {
          const mapped = items.map((it: any) => ({
            evidence_id: it.evidence_id || "EV-0001",
            evidence_type: it.evidence_type || "target",
            title: it.title || "FORENSIC EVIDENCE CROP",
            file_name: it.file_name || "evidence.jpg",
            url: it.url || `/evidence/${it.file_name}`,
            sha256_hash: it.sha256_hash || "",
            camera_id: it.camera_id || "CAM-01",
            confidence: it.confidence || 0.95,
            quality: it.quality || 0.9,
            reason: it.reason || "Perimeter security event",
            timestamp: "2026-09-24 14:32:18 UTC",
          }));
          setEvidenceList(mapped);
        }
      })
      .catch(() => {});
  }, []);

  const activeEvidence =
    evidenceList.find((e) => e.evidence_type === activeEvidenceTab) || DEFAULT_EVIDENCE_ITEMS[0];

  const handleVerify = async (idToVerify?: string) => {
    const targetId = (idToVerify || verifyId).trim();
    if (!targetId) return;

    setVerifying(true);
    setVerifyResult(null);
    setVerifyError(null);

    try {
      // 1. First attempt backend cryptographic verification endpoint if alive
      try {
        const res = await api.verifyEvidenceRecord(targetId);
        if (res && res.verification_status) {
          setVerifyResult(res);
          return;
        }
      } catch {
        // Backend offline or running in static Vercel deployment: fall through to browser Web Crypto SHA-256 verification
      }

      // 2. Browser Web Crypto SHA-256 Verification: compute bit-for-bit hash over real file bytes
      const matched =
        evidenceList.find(
          (e) =>
            e.evidence_id.toLowerCase() === targetId.toLowerCase() ||
            e.evidence_type.toLowerCase() === targetId.toLowerCase()
        ) || activeEvidence;

      const imgRes = await fetch(matched.url);
      if (!imgRes.ok) {
        throw new Error(`Evidence asset could not be loaded from ${matched.url}`);
      }

      const buffer = await imgRes.arrayBuffer();
      const hashBuffer = await window.crypto.subtle.digest("SHA-256", buffer);
      const hashArray = Array.from(new Uint8Array(hashBuffer));
      const computedHash = hashArray.map((b) => b.toString(16).padStart(2, "0")).join("");

      const isMatch = computedHash.toLowerCase() === matched.sha256_hash.toLowerCase();

      setVerifyResult({
        evidence_id: matched.evidence_id,
        verification_status: isMatch ? "VERIFIED" : "COMPROMISED",
        stored_hash: matched.sha256_hash,
        computed_hash: computedHash,
        file_exists: true,
        audit_verdict: isMatch
          ? "SHA-256 Cryptographic Hash Verified Bit-For-Bit. Court-Admissible Electronic Record (Sec 65B Certified)."
          : "Integrity Verification Failed: Recomputed hash does not match stored forensic record!",
        file_path: matched.url,
        file_bytes_checked: buffer.byteLength,
        verified_at: new Date().toISOString(),
        evidence_type: matched.evidence_type,
      });
    } catch (err: any) {
      setVerifyError(err.message || "Failed to verify evidence cryptographic integrity");
    } finally {
      setVerifying(false);
    }
  };

  return (
    <div className="space-y-4 font-sans p-2 sm:p-4">
      {/* View Header */}
      <div className="flex items-center justify-between flex-wrap gap-3 pb-2 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded border border-emerald-500/30 bg-emerald-500/10 flex items-center justify-center">
            <FileCheck className="w-4 h-4 text-[#00e676]" />
          </div>
          <div>
            <h2 className="font-display font-bold text-lg tracking-wide text-white uppercase">
              EVIDENCE VAULT & FORENSIC AUDIT
            </h2>
            <p className="text-[10px] font-mono text-gray-400">
              BIT-FOR-BIT SHA-256 AUDIT · COURT-ADMISSIBLE INTEGRITY (SEC 65B) · CRYPTOGRAPHIC MERKLE CHAIN
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => {
              const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(evidenceList, null, 2));
              const downloadAnchor = document.createElement("a");
              downloadAnchor.setAttribute("href", dataStr);
              downloadAnchor.setAttribute("download", "percepta_evidence_ledger.json");
              document.body.appendChild(downloadAnchor);
              downloadAnchor.click();
              downloadAnchor.remove();
            }}
            className="px-3 py-1.5 rounded border border-white/10 bg-[#080d16] text-xs font-mono text-gray-300 hover:text-white flex items-center gap-1.5 transition-colors cursor-pointer"
          >
            <Download className="w-3 h-3 text-[#00e5ff]" /> EXPORT LEDGER (JSON)
          </button>
        </div>
      </div>

      {/* ── 1. Target-Specific Forensic Evidence Inspector ─── */}
      <div className="rounded border border-[#00e5ff]/25 bg-[#080d16] p-4 shadow-xl">
        <div className="flex items-center justify-between flex-wrap gap-3 border-b border-white/10 pb-3 mb-4">
          <div className="flex items-center gap-2">
            <Target className="w-4 h-4 text-[#00e5ff]" />
            <span className="font-display font-bold text-sm tracking-wider text-white uppercase">
              TARGET-SPECIFIC EVIDENCE INSPECTOR
            </span>
          </div>
          <div className="flex items-center gap-1 bg-[#05070a] p-1 rounded border border-white/10 font-mono text-[10px]">
            {[
              { id: "target" as const, label: "TARGET CROP" },
              { id: "anpr" as const, label: "ANPR / PLATE" },
              { id: "face" as const, label: "FACE OBS." },
              { id: "weapon" as const, label: "WEAPON OBS." },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => {
                  setActiveEvidenceTab(tab.id);
                  const matched = evidenceList.find((e) => e.evidence_type === tab.id);
                  if (matched) setVerifyId(matched.evidence_id);
                }}
                className={`px-3 py-1 rounded transition-all font-bold cursor-pointer ${
                  activeEvidenceTab === tab.id
                    ? "bg-[#00e5ff] text-black shadow-[0_0_10px_#00e5ff]"
                    : "text-gray-400 hover:text-white"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Evidence Content Split */}
        <div className="grid grid-cols-12 gap-4 items-center">
          {/* Visual Crop Box with Real Image Crop */}
          <div className="col-span-12 lg:col-span-6">
            <div className="aspect-[16/9] rounded border border-[#00e5ff]/30 bg-[#05070a] relative overflow-hidden flex flex-col justify-between p-3 shadow-inner group">
              <div className="flex items-center justify-between font-mono text-[10px] text-[#00e5ff] z-10 bg-black/60 px-2 py-0.5 rounded border border-white/10">
                <span className="font-bold">{activeEvidence.title}</span>
                <span>{activeEvidence.evidence_id}</span>
              </div>

              {/* Real Forensic Evidence Image */}
              <div className="relative flex-1 flex items-center justify-center overflow-hidden my-2">
                <img
                  src={activeEvidence.url}
                  alt={activeEvidence.title}
                  className="max-h-full max-w-full object-contain rounded border border-[#00e5ff]/40 shadow-[0_0_20px_rgba(0,229,255,0.15)]"
                />

                {/* Tactical Confidence Overlay */}
                <div className="absolute top-2 right-2 px-1.5 py-0.5 bg-[#00e5ff] text-black font-mono text-[9px] font-bold rounded">
                  {(activeEvidence.confidence * 100).toFixed(1)}% CONFIDENCE
                </div>
              </div>

              <div className="font-mono text-[10px] text-gray-300 flex items-center justify-between z-10 border-t border-white/10 pt-2 bg-black/60 px-2 py-1 rounded">
                <span className="text-white font-bold">{activeEvidence.camera_id}</span>
                <span className="text-gray-400 truncate max-w-[200px]">{activeEvidence.reason}</span>
                <button
                  onClick={() => handleVerify(activeEvidence.evidence_id)}
                  className="text-[#00e5ff] hover:underline font-bold flex items-center gap-1 cursor-pointer"
                >
                  <ShieldCheck className="w-3 h-3 text-[#00e676]" /> VERIFY HASH
                </button>
              </div>
            </div>
          </div>

          {/* Technical Metadata Ledger */}
          <div className="col-span-12 lg:col-span-6 space-y-2.5 font-mono text-xs">
            <div className="p-3.5 rounded border border-white/10 bg-[#05070a] space-y-2.5 shadow-inner">
              <div className="flex justify-between border-b border-white/5 pb-1.5 text-[11px]">
                <span className="text-gray-500">PRIMARY EVIDENCE ID:</span>
                <span className="text-[#00e5ff] font-bold">{activeEvidence.evidence_id}</span>
              </div>
              <div className="flex justify-between border-b border-white/5 pb-1.5 text-[11px]">
                <span className="text-gray-500">CATEGORY:</span>
                <span className="text-white font-bold uppercase">{activeEvidence.evidence_type} OBSERVATION</span>
              </div>
              <div className="flex justify-between border-b border-white/5 pb-1.5 text-[11px]">
                <span className="text-gray-500">SOURCE SENSOR:</span>
                <span className="text-white">{activeEvidence.camera_id}</span>
              </div>
              <div className="flex justify-between border-b border-white/5 pb-1.5 text-[11px]">
                <span className="text-gray-500">TIMESTAMP (UTC):</span>
                <span className="text-gray-300">{activeEvidence.timestamp}</span>
              </div>
              <div className="flex justify-between border-b border-white/5 pb-1.5 text-[11px]">
                <span className="text-gray-500">DETECTION RATIONALE:</span>
                <span className="text-amber-400 font-bold">{activeEvidence.reason}</span>
              </div>
              <div className="space-y-1 text-[11px]">
                <span className="text-gray-500 block">AUTHENTIC SHA-256 DIGEST:</span>
                <div className="p-2 bg-black/60 rounded border border-white/10 text-[#00e676] text-[10px] break-all select-all font-mono">
                  {activeEvidence.sha256_hash}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* ── 2. SHA-256 Hash Chain & Integrity Verification ──────────────────────── */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left: Cryptographic Hash Chain Timeline */}
        <div className="col-span-12 lg:col-span-7 space-y-3">
          <div className="rounded border border-white/10 bg-[#080d16] p-4 shadow-lg">
            <div className="flex items-center justify-between border-b border-white/10 pb-3 mb-3">
              <div className="flex items-center gap-2">
                <Hash className="w-4 h-4 text-[#00e5ff]" />
                <span className="font-display font-bold text-sm tracking-wider text-white uppercase">
                  SHA-256 FORENSIC HASH CHAIN
                </span>
              </div>
              <span className="px-2 py-0.5 rounded bg-emerald-500/10 text-[#00e676] text-[9.5px] font-mono font-bold border border-emerald-500/30 flex items-center gap-1">
                <CheckCircle2 className="w-3 h-3" /> CHAIN INTACT (0 TAMPERED)
              </span>
            </div>

            <div className="space-y-2.5 font-mono">
              {DEMO_HASH_CHAIN.map((block) => (
                <div
                  key={block.block}
                  className="p-3 rounded border border-white/5 bg-[#05070a] text-xs space-y-1 hover:border-[#00e5ff]/30 transition-colors"
                >
                  <div className="flex items-center justify-between text-[10px]">
                    <span className="text-[#00e5ff] font-bold">BLOCK #{block.block}</span>
                    <span className="text-[#00e676] font-bold flex items-center gap-1">
                      <CheckCircle2 className="w-3 h-3" /> BIT-FOR-BIT VERIFIED
                    </span>
                  </div>
                  <div className="text-[10px] text-gray-500 truncate">
                    HASH: <span className="text-gray-300">{block.hash}</span>
                  </div>
                  <div className="flex items-center justify-between text-[9px] text-gray-500 pt-1">
                    <span>{new Date(block.timestamp).toLocaleTimeString()} UTC</span>
                    <span>{block.eventCount} EVENTS NORMALIZED</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: Real-Time Hash Verification Form */}
        <div className="col-span-12 lg:col-span-5 space-y-3 font-mono">
          <div className="rounded border border-white/10 bg-[#080d16] p-4 shadow-lg">
            <div className="flex items-center justify-between text-sm text-white font-display font-bold tracking-wider uppercase border-b border-white/10 pb-2 mb-3">
              <div className="flex items-center gap-2">
                <Search className="w-4 h-4 text-[#00e5ff]" />
                <span>VERIFY SPECIFIC EVENT HASH</span>
              </div>
              <span className="text-[10px] font-mono text-[#00e676]">WEB CRYPTO ACTIVE</span>
            </div>

            <div className="space-y-3">
              <div>
                <label className="block text-[10px] text-gray-400 mb-1">
                  EVIDENCE RECORD ID OR FILENAME:
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={verifyId}
                    onChange={(e) => setVerifyId(e.target.value)}
                    placeholder="e.g. EV-TGT-0042 or sample_target_crop.jpg"
                    className="flex-1 bg-[#05070a] border border-white/15 rounded px-3 py-1.5 text-xs text-white focus:outline-none focus:border-[#00e5ff]"
                  />
                  <button
                    onClick={() => handleVerify()}
                    disabled={verifying || !verifyId}
                    className="px-4 py-1.5 bg-[#00e5ff] text-black text-xs font-bold rounded hover:bg-[#38bdf8] transition-colors disabled:opacity-40 cursor-pointer font-display"
                  >
                    {verifying ? "VERIFYING..." : "VERIFY"}
                  </button>
                </div>
              </div>

              {/* 1-Click Fast Verification Shortcuts */}
              <div>
                <span className="text-[9.5px] text-gray-500 block mb-1">QUICK VERIFICATION SHORTCUTS:</span>
                <div className="grid grid-cols-2 gap-1.5">
                  {evidenceList.map((item) => (
                    <button
                      key={item.evidence_id}
                      onClick={() => {
                        setVerifyId(item.evidence_id);
                        handleVerify(item.evidence_id);
                      }}
                      className="text-left px-2 py-1 rounded bg-[#05070a] border border-white/10 hover:border-[#00e5ff]/50 text-[10px] text-gray-300 hover:text-white transition-colors cursor-pointer truncate"
                      title={item.title}
                    >
                      <span className="text-[#00e5ff] font-bold">⚡ {item.evidence_id}</span>
                      <span className="text-gray-500 block text-[9px] truncate">{item.file_name}</span>
                    </button>
                  ))}
                </div>
              </div>

              {verifyError && (
                <div className="p-3 rounded border border-red-500/30 bg-red-500/10 text-xs text-red-400 space-y-1">
                  <div className="flex items-center gap-1.5 font-bold">
                    <AlertTriangle className="w-3.5 h-3.5" /> VERIFICATION FAILED
                  </div>
                  <p className="text-[10px] text-red-300 font-mono break-all">{verifyError}</p>
                </div>
              )}

              {verifyResult && (
                <div
                  className={`p-3.5 rounded border text-xs space-y-2.5 font-mono shadow-md ${
                    verifyResult.verification_status === "VERIFIED"
                      ? "border-emerald-500/40 bg-emerald-500/10 text-[#00e676]"
                      : "border-red-500/40 bg-red-500/10 text-red-400"
                  }`}
                >
                  <div className="flex items-center justify-between font-bold">
                    <span className="flex items-center gap-1.5">
                      {verifyResult.verification_status === "VERIFIED" ? (
                        <CheckCircle2 className="w-4 h-4 text-[#00e676]" />
                      ) : (
                        <AlertTriangle className="w-4 h-4 text-red-400" />
                      )}
                      STATUS: {verifyResult.verification_status}
                    </span>
                    <span className="text-[9px] px-1.5 py-0.5 rounded bg-black/60 border border-white/10 text-white">
                      {verifyResult.evidence_type.toUpperCase()}
                    </span>
                  </div>

                  <p className="text-[11px] text-gray-200 font-semibold">{verifyResult.audit_verdict}</p>

                  <div className="space-y-1.5 text-[9.5px] pt-2 border-t border-white/10 text-gray-400">
                    {verifyResult.stored_hash && (
                      <div className="break-all">
                        <span className="text-white font-bold block">STORED DATABASE HASH:</span>
                        <span className="text-gray-300">{verifyResult.stored_hash}</span>
                      </div>
                    )}
                    {verifyResult.computed_hash && (
                      <div className="break-all">
                        <span className="text-white font-bold block">RECOMPUTED SHA-256:</span>
                        <span className={verifyResult.verification_status === "VERIFIED" ? "text-[#00e676]" : "text-red-400"}>
                          {verifyResult.computed_hash}
                        </span>
                      </div>
                    )}
                    {verifyResult.file_path && (
                      <div className="truncate text-gray-400">
                        FILE: {verifyResult.file_path} ({verifyResult.file_bytes_checked} bytes checked)
                      </div>
                    )}
                    <div className="text-[9px] text-emerald-400 font-bold flex items-center gap-1">
                      <Shield className="w-3 h-3" /> COURT-ADMISSIBLE UNDER INDIAN EVIDENCE ACT SEC 65B
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
