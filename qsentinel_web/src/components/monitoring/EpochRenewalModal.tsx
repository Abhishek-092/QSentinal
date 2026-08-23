"use client";

import { useState } from "react";
import { RefreshCw, AlertTriangle, CheckCircle2 } from "lucide-react";
import { api } from "@/lib/api/client";
import { EpochRecord, ApiError } from "@/lib/types/api";

interface EpochRenewalModalProps {
  streamId: string;
  epochId: string;
  onEpochRenewed: (newEpoch: EpochRecord) => void;
}

export function EpochRenewalModal({ streamId, epochId, onEpochRenewed }: EpochRenewalModalProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [calibrationP, setCalibrationP] = useState(0.02);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRenew = async () => {
    setIsSubmitting(true);
    setError(null);
    try {
      const newEpoch = await api.renewEpoch(streamId, epochId, {
        calibration_p: calibrationP,
        termination_reason: "EXPLICIT_OPERATOR_RENEWAL",
      });
      setIsOpen(false);
      onEpochRenewed(newEpoch);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError(`[${err.code}] ${err.message}`);
      } else {
        setError("Failed to execute epoch renewal.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <>
      <button
        onClick={() => setIsOpen(true)}
        className="px-3 py-1.5 bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 text-xs font-mono rounded transition-colors flex items-center gap-1.5"
      >
        <RefreshCw className="w-3.5 h-3.5" />
        RENEW EPOCH
      </button>

      {isOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-zinc-950 border border-zinc-800 rounded-lg max-w-md w-full p-6 space-y-4 shadow-2xl">
            <div className="flex items-center gap-2.5 text-amber-400 border-b border-zinc-800 pb-3">
              <AlertTriangle className="w-5 h-5 shrink-0" />
              <h3 className="text-sm font-bold font-mono">EXPLICIT EPOCH RENEWAL</h3>
            </div>

            <div className="space-y-3 text-xs text-zinc-300 font-sans">
              <p>
                Executing epoch renewal will close the current epoch{" "}
                <span className="font-mono text-amber-400">{epochId}</span> and spawn a new clean epoch index for stream{" "}
                <span className="font-mono text-zinc-200">{streamId}</span>.
              </p>
              <ul className="list-disc list-inside space-y-1 text-zinc-400 font-mono text-[11px]">
                <li>Historical evidence accumulators will NOT be silently reset.</li>
                <li>Existing sequence history remains permanently associated with the old epoch.</li>
                <li>New sequence numbering starts cleanly from k=1.</li>
              </ul>

              <div className="pt-2">
                <label className="block text-xs font-mono text-zinc-400 mb-1">
                  NEW OPERATING POINT CALIBRATION_P:
                </label>
                <input
                  type="number"
                  step="0.01"
                  min="0.0"
                  max="0.5"
                  value={calibrationP}
                  onChange={(e) => setCalibrationP(parseFloat(e.target.value))}
                  className="w-full px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-xs font-mono text-zinc-100 focus:outline-none focus:border-amber-500"
                />
              </div>

              {error && (
                <div className="p-2.5 bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono rounded">
                  {error}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3 pt-3 border-t border-zinc-800/80">
              <button
                onClick={() => setIsOpen(false)}
                disabled={isSubmitting}
                className="px-3 py-1.5 bg-zinc-900 hover:bg-zinc-800 text-zinc-400 text-xs font-mono rounded transition-colors"
              >
                CANCEL
              </button>
              <button
                onClick={handleRenew}
                disabled={isSubmitting}
                className="px-4 py-1.5 bg-amber-600 hover:bg-amber-500 text-zinc-950 font-bold text-xs font-mono rounded transition-colors flex items-center gap-2"
              >
                {isSubmitting ? (
                  <>
                    <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                    EXECUTING RENEWAL...
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-3.5 h-3.5" />
                    CONFIRM RENEWAL
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
