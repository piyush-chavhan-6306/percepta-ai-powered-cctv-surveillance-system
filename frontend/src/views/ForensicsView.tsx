import React, { useState } from "react";
import { useSurveillance } from "../store/surveillanceContext";
import { api } from "../api/client";
import type { ForensicVerificationResult, IntegrityAuditReport } from "../types/surveillance";
import {
  FileCheck,
  Key,
  Database,
  Search,
  AlertCircle,
  Download,
  Loader2,
  RefreshCw,
} from "lucide-react";

export const ForensicsView: React.FC = () => {
  const { alerts } = useSurveillance();

  const [verifyEventId, setVerifyEventId] = useState<string>(alerts[0]?.event_id || "");
  const [verificationResult, setVerificationResult] = useState<ForensicVerificationResult | null>(null);
  const [isVerifying, setIsVerifying] = useState<boolean>(false);
  const [verifyError, setVerifyError] = useState<string | null>(null);

  // Full Database Integrity Audit
  const [isAuditing, setIsAuditing] = useState<boolean>(false);
  const [auditReport, setAuditReport] = useState<IntegrityAuditReport | null>(null);
  const [auditError, setAuditError] = useState<string | null>(null);

  const handleVerifyEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!verifyEventId.trim()) return;

    setIsVerifying(true);
    setVerifyError(null);
    try {
      const res = await api.verifyEvent(verifyEventId.trim());
      setVerificationResult(res);
    } catch (err: any) {
      setVerifyError(err.message || "Failed to verify event");
      setVerificationResult(null);
    } finally {
      setIsVerifying(false);
    }
  };

  const handleRunAudit = async () => {
    setIsAuditing(true);
    setAuditError(null);
    try {
      const report = await api.auditIntegrity(200);
      setAuditReport(report);
    } catch (err: any) {
      setAuditError(err.message || "Integrity audit failed");
    } finally {
      setIsAuditing(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="flex items-center justify-between flex-wrap gap-3 bg-[#0a0f18] border border-white/10 p-3 rounded-sm">
        <div className="flex items-center gap-2.5">
          <FileCheck className="w-5 h-5 text-[#00e5ff]" />
          <div>
            <h3 className="font-display font-bold text-base tracking-wider text-white">
              EVIDENCE INTEGRITY & CRYPTOGRAPHIC CHAIN OF CUSTODY
            </h3>
            <p className="font-mono-tech text-[11px] text-gray-400">
              SHA-256 digital signature verification & SQLite WAL Merkle hash audit
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <a
            href={api.getExportUrl("json")}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded text-xs font-display font-bold flex items-center gap-1.5 transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-[#00e5ff]" />
            <span>EXPORT JSON</span>
          </a>
          <a
            href={api.getExportUrl("csv")}
            target="_blank"
            rel="noopener noreferrer"
            className="px-3 py-1.5 bg-white/5 hover:bg-white/10 text-gray-300 border border-white/10 rounded text-xs font-display font-bold flex items-center gap-1.5 transition-colors"
          >
            <Download className="w-3.5 h-3.5 text-[#00e676]" />
            <span>EXPORT CSV</span>
          </a>
        </div>
      </div>

      {/* Main Layout Grid */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column (6 cols): Single-Event SHA-256 Verifier */}
        <div className="col-span-12 lg:col-span-6 space-y-4">
          <div className="bg-[#090d14] border border-white/10 rounded-sm p-4 space-y-4">
            <div className="flex items-center gap-2 text-xs font-display font-bold text-white border-b border-white/10 pb-2">
              <Key className="w-4 h-4 text-[#00e5ff]" />
              <span>SINGLE-EVENT CRYPTOGRAPHIC VERIFIER</span>
            </div>

            <form onSubmit={handleVerifyEvent} className="space-y-3">
              <div>
                <label className="block text-[11px] font-mono-tech text-gray-400 mb-1">
                  EVENT / ALERT ID TO VERIFY
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    required
                    value={verifyEventId}
                    onChange={(e) => setVerifyEventId(e.target.value)}
                    placeholder="Enter event ID (e.g. EVT-01, ALT-001)"
                    className="flex-1 bg-[#060a12] border border-white/10 rounded px-3 py-2 text-xs font-mono-tech text-white focus:outline-none focus:border-[#00e5ff]"
                  />
                  <button
                    type="submit"
                    disabled={isVerifying}
                    className="px-4 py-2 bg-[#00e5ff] hover:bg-[#00cce6] text-black font-display font-bold text-xs rounded flex items-center gap-1.5 transition-colors"
                  >
                    {isVerifying ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Search className="w-3.5 h-3.5" />
                    )}
                    <span>VERIFY HASH</span>
                  </button>
                </div>
              </div>
            </form>

            {verifyError && (
              <div className="p-3 bg-red-500/15 border border-red-500/30 rounded text-red-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{verifyError}</span>
              </div>
            )}

            {verificationResult && (
              <div className="p-3.5 bg-[#060a12] border border-white/10 rounded space-y-2.5 text-xs font-mono-tech">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">VERIFICATION STATUS</span>
                  <span
                    className={`px-2 py-0.5 rounded font-bold uppercase ${
                      verificationResult.is_authentic
                        ? "bg-emerald-500/20 text-[#00e676] border border-emerald-500/30"
                        : "bg-red-500/20 text-red-400 border border-red-500/30"
                    }`}
                  >
                    {verificationResult.is_authentic ? "AUTHENTIC • UNTAMPERED" : "SIGNATURE MISMATCH"}
                  </span>
                </div>

                <div className="space-y-1 pt-1 text-[11px]">
                  <div>
                    <span className="text-gray-500 block text-[10px]">EVENT ID & TYPE</span>
                    <span className="text-white font-bold">{verificationResult.event_id} ({verificationResult.event_type})</span>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-[10px]">COMPUTED SHA-256 HASH</span>
                    <code className="text-[#00e5ff] break-all">{verificationResult.computed_sha256_hash}</code>
                  </div>
                  <div>
                    <span className="text-gray-500 block text-[10px]">TAMPER AUDIT STATUS</span>
                    <span className="text-gray-300">{verificationResult.tamper_status}</span>
                  </div>
                </div>

                <p className="text-gray-400 text-[10px] pt-1 border-t border-white/5">
                  Verified at {new Date(verificationResult.verification_timestamp).toLocaleString()}
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Right Column (6 cols): Database Integrity Audit */}
        <div className="col-span-12 lg:col-span-6 space-y-4">
          <div className="bg-[#090d14] border border-white/10 rounded-sm p-4 space-y-4">
            <div className="flex items-center justify-between border-b border-white/10 pb-2">
              <div className="flex items-center gap-2 text-xs font-display font-bold text-white">
                <Database className="w-4 h-4 text-[#00e676]" />
                <span>DATABASE MERKLE ROOT INTEGRITY AUDIT</span>
              </div>

              <button
                type="button"
                onClick={handleRunAudit}
                disabled={isAuditing}
                className="px-3 py-1.5 bg-[#00e676] hover:bg-[#00c864] text-black font-display font-bold text-xs rounded flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                {isAuditing ? (
                  <>
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    <span>AUDITING...</span>
                  </>
                ) : (
                  <>
                    <RefreshCw className="w-3.5 h-3.5" />
                    <span>RUN INTEGRITY AUDIT</span>
                  </>
                )}
              </button>
            </div>

            {auditError && (
              <div className="p-3 bg-red-500/15 border border-red-500/30 rounded text-red-300 text-xs flex items-center gap-2">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <span>{auditError}</span>
              </div>
            )}

            {auditReport ? (
              <div className="p-3.5 bg-[#060a12] border border-white/10 rounded space-y-3 text-xs font-mono-tech">
                <div className="flex items-center justify-between">
                  <span className="text-gray-400">AUDIT VERDICT</span>
                  <span
                    className={`px-2 py-0.5 rounded font-bold uppercase ${
                      auditReport.audit_verdict === "PASS_INTEGRITY_VERIFIED"
                        ? "bg-emerald-500/20 text-[#00e676] border border-emerald-500/30"
                        : "bg-red-500/20 text-red-400 border border-red-500/30"
                    }`}
                  >
                    {auditReport.audit_verdict}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-[11px]">
                  <div className="bg-black/40 p-2 rounded border border-white/5">
                    <span className="text-gray-500 block text-[9px]">TOTAL SCANNED</span>
                    <span className="text-white font-bold">{auditReport.total_records_checked}</span>
                  </div>
                  <div className="bg-black/40 p-2 rounded border border-white/5">
                    <span className="text-gray-500 block text-[9px]">AUTHENTIC</span>
                    <span className="text-[#00e676] font-bold">{auditReport.authentic_count}</span>
                  </div>
                  <div className="bg-black/40 p-2 rounded border border-white/5">
                    <span className="text-gray-500 block text-[9px]">TAMPERED</span>
                    <span className="text-[#ff1744] font-bold">{auditReport.tampered_count}</span>
                  </div>
                </div>

                <div className="pt-1">
                  <span className="text-gray-500 block text-[10px]">ROOT MERKLE CHAIN HASH</span>
                  <code className="text-[#00e5ff] text-[11px] break-all">
                    {auditReport.root_chain_hash}
                  </code>
                </div>

                <div className="text-[10px] text-gray-500">
                  Audited at {new Date(auditReport.audit_timestamp).toLocaleString()}
                </div>
              </div>
            ) : (
              <div className="p-8 text-center text-gray-500 font-mono-tech text-xs">
                Click "Run Integrity Audit" to recalculate and verify all SHA-256 event hashes in the database.
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
