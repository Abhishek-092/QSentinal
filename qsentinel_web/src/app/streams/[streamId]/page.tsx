"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { Header } from "@/components/layout/Header";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { StreamRecord, EpochRecord, ApiError } from "@/lib/types/api";
import { Layers, Plus, ArrowRight, ArrowLeft, RefreshCw, AlertCircle } from "lucide-react";

export default function StreamDetailPage({ params }: { params: Promise<{ streamId: string }> }) {
  const resolvedParams = use(params);
  const streamId = resolvedParams.streamId;

  const [stream, setStream] = useState<StreamRecord | null>(null);
  const [epochs, setEpochs] = useState<EpochRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Epoch Creation state
  const [calibrationP, setCalibrationP] = useState(0.02);
  const [isCreatingEpoch, setIsCreatingEpoch] = useState(false);
  const [epochCreateError, setEpochCreateError] = useState<string | null>(null);

  useEffect(() => {
    async function loadStreamDetails() {
      try {
        const st = await api.getStream(streamId);
        setStream(st);
      } catch (err: unknown) {
        if (err instanceof ApiError && err.status === 404) {
          setError(`Stream ${streamId} not found.`);
        } else {
          setError("Failed to load stream details.");
        }
      } finally {
        setLoading(false);
      }
    }
    loadStreamDetails();
  }, [streamId]);

  const handleCreateEpoch = async () => {
    setIsCreatingEpoch(true);
    setEpochCreateError(null);
    try {
      const ep = await api.createEpoch(streamId, { calibration_p: calibrationP });
      setEpochs((prev) => [ep, ...prev]);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setEpochCreateError(`[${err.code}] ${err.message}`);
      } else {
        setEpochCreateError("Failed to create epoch.");
      }
    } finally {
      setIsCreatingEpoch(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans">
      <Header isHealthy={true} isReady={true} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <div className="flex items-center gap-4">
          <Link href="/streams" className="p-2 bg-zinc-900 border border-zinc-800 rounded text-zinc-400 hover:text-zinc-200">
            <ArrowLeft className="w-4 h-4" />
          </Link>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold tracking-tight text-zinc-100 font-mono">{streamId}</h1>
              {stream && <StatusBadge status={stream.status} />}
            </div>
            <p className="text-xs text-zinc-400 mt-0.5">{stream?.description || "Logical Monitoring Stream"}</p>
          </div>
        </div>

        {/* Stream Hierarchy Navigation Diagram */}
        <div className="p-4 bg-zinc-900/40 border border-zinc-800 rounded font-mono text-xs text-zinc-400 flex items-center justify-between overflow-x-auto">
          <div className="flex items-center gap-2">
            <span className="text-emerald-400 font-bold">STREAM</span>
            <span>→</span>
            <span className="text-zinc-300">EPOCH LIFECYCLE</span>
            <span>→</span>
            <span className="text-zinc-500">SESSION SEQUENCE</span>
            <span>→</span>
            <span className="text-zinc-500">DETECTOR STATE</span>
          </div>
          <button
            onClick={handleCreateEpoch}
            disabled={isCreatingEpoch}
            className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-zinc-950 font-bold rounded transition-colors flex items-center gap-1.5 shrink-0"
          >
            <Plus className="w-3.5 h-3.5" />
            CREATE EPOCH
          </button>
        </div>

        {epochCreateError && (
          <div className="p-3 bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono rounded">
            {epochCreateError}
          </div>
        )}

        {/* Epochs List */}
        <div className="border border-zinc-800 rounded bg-zinc-950/60 overflow-hidden space-y-0">
          <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-400" />
              <h2 className="text-sm font-bold font-mono text-zinc-200">BOUND MULTI-DETECTOR EPOCHS</h2>
            </div>
            <span className="text-xs font-mono text-zinc-500">{epochs.length} EPOCHS</span>
          </div>

          {loading ? (
            <div className="p-8 text-center text-xs font-mono text-zinc-500">LOADING EPOCHS...</div>
          ) : epochs.length === 0 ? (
            <div className="p-12 text-center space-y-3">
              <p className="text-xs font-mono text-zinc-400">NO ACTIVE EPOCHS FOUND FOR THIS STREAM</p>
              <p className="text-xs text-zinc-500 max-w-md mx-auto">
                Create an epoch to initialize Stage 1, Stage 2, and Change-Point detectors under a bound calibration context.
              </p>
              <button
                onClick={handleCreateEpoch}
                className="px-3 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-zinc-950 font-bold text-xs font-mono rounded transition-colors"
              >
                SPAWN EPOCH 1
              </button>
            </div>
          ) : (
            <div className="divide-y divide-zinc-800">
              {epochs.map((ep) => (
                <div key={ep.epoch_id} className="p-5 flex items-center justify-between hover:bg-zinc-900/40 transition-colors">
                  <div className="space-y-1 font-mono">
                    <div className="flex items-center gap-3">
                      <span className="text-xs text-zinc-400 font-bold">EPOCH #{ep.epoch_index}</span>
                      <span className="text-xs text-zinc-200">{ep.epoch_id}</span>
                      <StatusBadge status={ep.status} />
                    </div>
                    <div className="text-[11px] text-zinc-500 flex gap-4 pt-1">
                      <span>CALIBRATION_P: {String(ep.calibration_context.calibration_p)}</span>
                      <span>CREATED: {ep.created_at}</span>
                    </div>
                  </div>

                  <Link
                    href={`/streams/${streamId}/epochs/${ep.epoch_id}`}
                    className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-mono rounded transition-colors flex items-center gap-1 shrink-0"
                  >
                    MONITOR CONSOLE <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
