import React, { useState } from "react";
import { useSurveillance } from "../store/surveillanceContext";
import { api } from "../api/client";
import {
  Bot,
  Send,
  ShieldCheck,
  Database,
  Sparkles,
  AlertCircle,
  Loader2,
  CheckCircle2,
} from "lucide-react";

interface ChatItem {
  id: string;
  sender: "user" | "assistant";
  queryText?: string;
  response?: {
    observed_facts: string[];
    rule_results: string[];
    interpretation: string;
    is_refusal?: boolean;
  };
  plainText?: string;
  timestamp: string;
}

export const IntelligenceView: React.FC = () => {
  const { cameras } = useSurveillance();
  const [query, setQuery] = useState<string>("");
  const [selectedCameraId, setSelectedCameraId] = useState<string>("");
  const [isThinking, setIsThinking] = useState<boolean>(false);
  const [chatHistory, setChatHistory] = useState<ChatItem[]>([
    {
      id: "init",
      sender: "assistant",
      plainText:
        "Greetings, Operator. I am your Grounded AI Intelligence Assistant. All answers are strictly grounded in active SQLite WAL surveillance records. I refuse ungrounded biometrics, weapon claims, or subjective intent speculation.",
      timestamp: new Date().toLocaleTimeString(),
    },
  ]);

  const presetQueries = [
    "What targets crossed the perimeter boundary?",
    "Show dwell time for Track 1.",
    "Summarize recent critical incidents.",
    "Did Track 2 enter any restricted zone?",
    "What is the identity of the person on Camera 1? (Test refusal guardrail)",
    "Do any targets have weapons? (Test refusal guardrail)",
  ];

  const handleSendQuery = async (textToSend?: string) => {
    const q = (textToSend || query).trim();
    if (!q) return;

    const userMsg: ChatItem = {
      id: `user-${Date.now()}`,
      sender: "user",
      queryText: q,
      timestamp: new Date().toLocaleTimeString(),
    };

    setChatHistory((prev) => [...prev, userMsg]);
    setQuery("");
    setIsThinking(true);

    try {
      const res = await api.queryIntelligence(q, selectedCameraId || undefined);

      const assistantMsg: ChatItem = {
        id: `asst-${Date.now()}`,
        sender: "assistant",
        response: {
          observed_facts: res.observed_facts || [],
          rule_results: res.rule_results || [],
          interpretation: res.interpretation || "",
          is_refusal: res.status === "refused" || res.grounding_status === "refused",
        },
        timestamp: new Date().toLocaleTimeString(),
      };

      setChatHistory((prev) => [...prev, assistantMsg]);
    } catch (err: any) {
      const errorMsg: ChatItem = {
        id: `err-${Date.now()}`,
        sender: "assistant",
        plainText: `Query error: ${err.message || "Failed to contact intelligence engine"}`,
        timestamp: new Date().toLocaleTimeString(),
      };
      setChatHistory((prev) => [...prev, errorMsg]);
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Top Banner */}
      <div className="flex items-center justify-between flex-wrap gap-3 bg-[#0a0f18] border border-white/10 p-3 rounded-sm">
        <div className="flex items-center gap-2.5">
          <Bot className="w-5 h-5 text-[#00e5ff]" />
          <div>
            <h3 className="font-display font-bold text-base tracking-wider text-white">
              GROUNDED AI SURVEILLANCE ASSISTANT
            </h3>
            <p className="font-mono-tech text-[11px] text-gray-400">
              3-Tier explainable reasoning directly querying verified SQLite database records
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="flex items-center gap-1 text-[10px] font-mono-tech px-2 py-0.5 bg-[#00e676]/15 text-[#00e676] border border-[#00e676]/30 rounded">
            <ShieldCheck className="w-3 h-3" />
            <span>ANTI-HALLUCINATION GUARDRAILS ACTIVE</span>
          </span>
        </div>
      </div>

      {/* Main Chat Layout */}
      <div className="grid grid-cols-12 gap-4">
        {/* Left Column (8 cols): Chat Stream */}
        <div className="col-span-12 lg:col-span-8 bg-[#090d14] border border-white/10 rounded-sm flex flex-col min-h-[640px]">
          {/* Chat Messages */}
          <div className="flex-1 p-4 overflow-y-auto space-y-4 max-h-[580px]">
            {chatHistory.map((msg) => (
              <div
                key={msg.id}
                className={`flex gap-3 ${
                  msg.sender === "user" ? "justify-end" : "justify-start"
                }`}
              >
                {msg.sender === "assistant" && (
                  <div className="w-7 h-7 rounded-sm bg-[#00e5ff]/20 border border-[#00e5ff]/40 flex items-center justify-center shrink-0">
                    <Bot className="w-4 h-4 text-[#00e5ff]" />
                  </div>
                )}

                <div
                  className={`max-w-2xl rounded p-3.5 space-y-2 text-xs ${
                    msg.sender === "user"
                      ? "bg-[#14233a] border border-[#00e5ff]/30 text-white"
                      : "bg-[#060a12] border border-white/10 text-gray-200"
                  }`}
                >
                  <div className="flex items-center justify-between text-[10px] font-mono-tech text-gray-400 mb-1 border-b border-white/5 pb-1">
                    <span className="font-bold uppercase text-[#00e5ff]">
                      {msg.sender === "user" ? "DUTY OPERATOR" : "GROUNDED AI REASONER"}
                    </span>
                    <span>{msg.timestamp}</span>
                  </div>

                  {msg.plainText && <p className="font-sans leading-relaxed">{msg.plainText}</p>}

                  {msg.queryText && <p className="font-sans leading-relaxed font-semibold">{msg.queryText}</p>}

                  {msg.response && (
                    <div className="space-y-3 pt-1">
                      {msg.response.is_refusal ? (
                        <div className="p-3 bg-red-500/15 border border-red-500/30 rounded text-red-300 space-y-1">
                          <div className="flex items-center gap-1.5 font-display font-bold text-red-400">
                            <AlertCircle className="w-4 h-4" />
                            <span>GUARDRAIL REFUSAL NOTICE</span>
                          </div>
                          <p className="font-sans text-xs">
                            {msg.response.interpretation}
                          </p>
                        </div>
                      ) : (
                        <>
                          {/* 1. Observed Facts */}
                          {msg.response.observed_facts.length > 0 && (
                            <div className="p-2.5 bg-black/40 border border-white/10 rounded space-y-1">
                              <div className="text-[10px] font-mono-tech font-bold text-[#00e5ff] uppercase flex items-center gap-1">
                                <Database className="w-3 h-3" />
                                <span>[OBSERVED FACTS — SQLITE DISK TRUTH]</span>
                              </div>
                              <ul className="list-disc pl-4 space-y-0.5 text-gray-300 font-mono-tech text-[11px]">
                                {msg.response.observed_facts.map((fact, idx) => (
                                  <li key={idx}>{fact}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {/* 2. Deterministic Rule Result */}
                          {msg.response.rule_results.length > 0 && (
                            <div className="p-2.5 bg-black/40 border border-white/10 rounded space-y-1">
                              <div className="text-[10px] font-mono-tech font-bold text-[#ffab00] uppercase flex items-center gap-1">
                                <ShieldCheck className="w-3 h-3" />
                                <span>[DETERMINISTIC RULE EVALUATION]</span>
                              </div>
                              <ul className="list-disc pl-4 space-y-0.5 text-gray-300 font-mono-tech text-[11px]">
                                {msg.response.rule_results.map((rule, idx) => (
                                  <li key={idx}>{rule}</li>
                                ))}
                              </ul>
                            </div>
                          )}

                          {/* 3. Grounded Interpretation */}
                          {msg.response.interpretation && (
                            <div className="p-2.5 bg-[#0a121e] border border-[#00e5ff]/20 rounded space-y-1">
                              <div className="text-[10px] font-mono-tech font-bold text-emerald-400 uppercase flex items-center gap-1">
                                <CheckCircle2 className="w-3 h-3" />
                                <span>[GROUNDED AI SYNTHESIS]</span>
                              </div>
                              <p className="text-gray-100 font-sans text-xs leading-relaxed">
                                {msg.response.interpretation}
                              </p>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}

            {isThinking && (
              <div className="flex items-center gap-2 p-3 text-xs font-mono-tech text-[#00e5ff]">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>Querying SQLite WAL database and evaluating deterministic rules...</span>
              </div>
            )}
          </div>

          {/* Input Box */}
          <div className="p-3 bg-[#0e141f] border-t border-white/10 flex flex-col gap-2">
            <div className="flex items-center gap-2">
              <select
                value={selectedCameraId}
                onChange={(e) => setSelectedCameraId(e.target.value)}
                className="bg-[#060a12] border border-white/10 rounded px-2.5 py-1 text-[11px] font-mono-tech text-gray-300 focus:outline-none focus:border-[#00e5ff]"
              >
                <option value="">All Cameras</option>
                {cameras.map((c) => (
                  <option key={c.camera_id} value={c.camera_id}>
                    {c.camera_id} ({c.name})
                  </option>
                ))}
              </select>
            </div>

            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSendQuery();
              }}
              className="flex gap-2"
            >
              <input
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Ask grounded questions (e.g. 'What targets crossed the perimeter?')..."
                className="flex-1 bg-[#060a12] border border-white/10 rounded px-3 py-2 text-xs text-white font-sans focus:outline-none focus:border-[#00e5ff]"
              />
              <button
                type="submit"
                disabled={isThinking || !query.trim()}
                className="px-4 py-2 bg-[#00e5ff] hover:bg-[#00cce6] text-black font-display font-bold text-xs rounded flex items-center gap-1.5 transition-colors disabled:opacity-50"
              >
                <Send className="w-3.5 h-3.5" />
                <span>QUERY</span>
              </button>
            </form>
          </div>
        </div>

        {/* Right Column (4 cols): Preset Queries & Guardrail Explanations */}
        <div className="col-span-12 lg:col-span-4 space-y-4">
          <div className="bg-[#090d14] border border-white/10 rounded-sm p-4 space-y-3">
            <div className="flex items-center gap-2 text-xs font-display font-bold text-white border-b border-white/10 pb-2">
              <Sparkles className="w-4 h-4 text-[#00e5ff]" />
              <span>TESTED EVALUATION QUERIES</span>
            </div>

            <div className="space-y-1.5">
              {presetQueries.map((preset, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSendQuery(preset)}
                  className="w-full text-left p-2 bg-[#060a12] hover:bg-[#121a28] border border-white/5 hover:border-[#00e5ff]/40 rounded text-[11px] text-gray-300 font-sans transition-colors"
                >
                  {preset}
                </button>
              ))}
            </div>
          </div>

          <div className="bg-[#090d14] border border-white/10 rounded-sm p-4 space-y-2 text-xs font-mono-tech text-gray-400">
            <div className="text-white font-display font-bold text-xs flex items-center gap-1.5 border-b border-white/10 pb-2">
              <ShieldCheck className="w-4 h-4 text-[#00e676]" />
              <span>ANTI-HALLUCINATION POLICY</span>
            </div>
            <p className="text-[11px] leading-relaxed">
              • <strong>No Speculation</strong>: Zero answers are generated without backing database rows.
            </p>
            <p className="text-[11px] leading-relaxed">
              • <strong>Biometric Refusal</strong>: Explicitly refuses identifying individuals or faces.
            </p>
            <p className="text-[11px] leading-relaxed">
              • <strong>Weapon & Intent Refusal</strong>: Refuses weapon presence claims or subjective intent deductions without certified sensors.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
