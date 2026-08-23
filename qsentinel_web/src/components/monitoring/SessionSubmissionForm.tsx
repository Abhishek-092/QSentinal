"use client";

import { useState } from "react";
import { Send, RefreshCw, AlertCircle, CheckCircle } from "lucide-react";
import { api } from "@/lib/api/client";
import { generateSampleTranscript } from "@/lib/utils/transcriptGenerator";
import { UnifiedMonitoringResult, ApiError } from "@/lib/types/api";

interface SessionSubmissionFormProps {
  streamId: string;
  epochId: string;
  onSessionProcessed: (result: UnifiedMonitoringResult) => void;
}

export function SessionSubmissionForm({ streamId, epochId, onSessionProcessed }: SessionSubmissionFormProps) {
  const [noiseP, setNoiseP] = useState(0.02);
  const [customSessionId, setCustomSessionId] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [notice, setNotice] = useState<{ type: "success" | "duplicate" | "conflict" | "error"; message: string } | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    setNotice(null);

    const transcript = generateSampleTranscript(customSessionId.trim() || undefined, noiseP);

    try {
      const res = await api.submitSession(streamId, epochId, transcript);
      setNotice({ type: "success", message: `Session ${res.session_id} processed successfully (Sequence #${res.sequence_number}).` });
      onSessionProcessed(res);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        if (err.code === "CONFLICTING_SESSION_ID") {
          setNotice({
            type: "conflict",
            message: "HTTP 409 CONFLICT: Session ID already exists with conflicting transcript content!",
          });
        } else if (err.code === "EPOCH_CLOSED") {
          setNotice({ type: "error", message: "HTTP 409 CONFLICT: Target Epoch is CLOSED or TERMINAL." });
        } else {
          setNotice({ type: "error", message: `[${err.code}] ${err.message}` });
        }
      } else {
        setNotice({ type: "error", message: "Network submission failure." });
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="p-4 border border-zinc-800 rounded bg-zinc-950/60 space-y-4">
      <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
        <div className="flex items-center gap-2">
          <Send className="w-4 h-4 text-emerald-400" />
          <h3 className="text-sm font-semibold text-zinc-200">SESSION TRANSMISSION INTERFACE</h3>
        </div>
        <span className="text-xs font-mono text-zinc-500">POST /sessions</span>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-mono text-zinc-400 mb-1.5">
              NOISE PARAMETER (p): <span className="text-emerald-400">{noiseP}</span>
            </label>
            <input
              type="range"
              min="0.0"
              max="0.15"
              step="0.01"
              value={noiseP}
              onChange={(e) => setNoiseP(parseFloat(e.target.value))}
              className="w-full h-1.5 bg-zinc-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
            />
            <div className="flex justify-between text-[10px] font-mono text-zinc-500 mt-1">
              <span>0.00 (Nominal)</span>
              <span>0.05 (Standard)</span>
              <span>0.15 (Anomalous)</span>
            </div>
          </div>

          <div>
            <label className="block text-xs font-mono text-zinc-400 mb-1.5">
              CUSTOM SESSION ID (OPTIONAL FOR IDEMPOTENCY / CONFLICT TESTING):
            </label>
            <input
              type="text"
              placeholder="e.g. sess-fixed-123"
              value={customSessionId}
              onChange={(e) => setCustomSessionId(e.target.value)}
              className="w-full px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-xs font-mono text-zinc-200 focus:outline-none focus:border-emerald-500"
            />
          </div>
        </div>

        {notice && (
          <div
            className={`p-3 rounded text-xs font-mono flex items-start gap-2.5 border ${
              notice.type === "success"
                ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-300"
                : notice.type === "conflict"
                ? "bg-rose-500/10 border-rose-500/30 text-rose-300"
                : "bg-red-500/10 border-red-500/30 text-red-300"
            }`}
          >
            {notice.type === "success" ? (
              <CheckCircle className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            ) : (
              <AlertCircle className="w-4 h-4 text-red-400 shrink-0 mt-0.5" />
            )}
            <div>{notice.message}</div>
          </div>
        )}

        <div className="flex justify-end">
          <button
            type="submit"
            disabled={isSubmitting}
            className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-zinc-800 disabled:text-zinc-500 text-zinc-950 font-semibold rounded text-xs font-mono transition-colors flex items-center gap-2"
          >
            {isSubmitting ? (
              <>
                <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                TRANSMITTING...
              </>
            ) : (
              <>
                <Send className="w-3.5 h-3.5" />
                TRANSMIT SESSION TRANSCRIPT
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
