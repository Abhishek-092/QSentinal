"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { Header } from "@/components/layout/Header";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { StreamRecord, ApiError } from "@/lib/types/api";
import { Layers, Plus, ArrowRight, AlertCircle } from "lucide-react";

export default function StreamsPage() {
  const [streams, setStreams] = useState<StreamRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [newStreamId, setNewStreamId] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [createError, setCreateError] = useState<string | null>(null);

  useEffect(() => {
    async function loadStreams() {
      try {
        // Try loading initial standard stream
        const sample = await api.getStream("stream-alice-bob-01");
        setStreams([sample]);
      } catch {
        setStreams([]);
      } finally {
        setLoading(false);
      }
    }
    loadStreams();
  }, []);

  const handleCreateStream = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStreamId.trim()) return;

    setIsCreating(true);
    setCreateError(null);

    try {
      const created = await api.createStream({
        stream_id: newStreamId.trim(),
        description: newDesc.trim(),
      });
      setStreams((prev) => [...prev, created]);
      setNewStreamId("");
      setNewDesc("");
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setCreateError(`[${err.code}] ${err.message}`);
      } else {
        setCreateError("Failed to create stream.");
      }
    } finally {
      setIsCreating(false);
    }
  };

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans">
      <Header isHealthy={true} isReady={true} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        <div className="border-b border-zinc-800 pb-6">
          <h1 className="text-2xl font-bold tracking-tight text-zinc-100 font-mono">
            STREAM MANAGEMENT // LOGICAL CHANNELS
          </h1>
          <p className="text-sm text-zinc-400 mt-1">
            Register and inspect long-lived quantum channel monitoring streams.
          </p>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Create Stream Form */}
          <div className="p-6 bg-zinc-950 border border-zinc-800 rounded space-y-4 h-fit">
            <div className="flex items-center gap-2 border-b border-zinc-800 pb-3">
              <Plus className="w-4 h-4 text-emerald-400" />
              <h2 className="text-sm font-bold font-mono text-zinc-200">REGISTER NEW STREAM</h2>
            </div>

            <form onSubmit={handleCreateStream} className="space-y-4">
              <div>
                <label className="block text-xs font-mono text-zinc-400 mb-1">STREAM IDENTIFIER:</label>
                <input
                  type="text"
                  required
                  placeholder="e.g. stream-qds-01"
                  value={newStreamId}
                  onChange={(e) => setNewStreamId(e.target.value)}
                  className="w-full px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-xs font-mono text-zinc-200 focus:outline-none focus:border-emerald-500"
                />
              </div>

              <div>
                <label className="block text-xs font-mono text-zinc-400 mb-1">DESCRIPTION:</label>
                <textarea
                  rows={3}
                  placeholder="Operational details or channel notes..."
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                  className="w-full px-3 py-1.5 bg-zinc-900 border border-zinc-800 rounded text-xs font-mono text-zinc-200 focus:outline-none focus:border-emerald-500"
                />
              </div>

              {createError && (
                <div className="p-2.5 bg-red-500/10 border border-red-500/30 text-red-400 text-xs font-mono rounded">
                  {createError}
                </div>
              )}

              <button
                type="submit"
                disabled={isCreating}
                className="w-full py-2 bg-emerald-600 hover:bg-emerald-500 text-zinc-950 font-bold text-xs font-mono rounded transition-colors disabled:opacity-50"
              >
                {isCreating ? "REGISTERING..." : "REGISTER STREAM"}
              </button>
            </form>
          </div>

          {/* Streams List */}
          <div className="lg:col-span-2 border border-zinc-800 rounded bg-zinc-950/60 overflow-hidden">
            <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Layers className="w-4 h-4 text-emerald-400" />
                <h2 className="text-sm font-bold font-mono text-zinc-200">REGISTERED MONITORING STREAMS</h2>
              </div>
              <span className="text-xs font-mono text-zinc-500">{streams.length} STREAMS</span>
            </div>

            {loading ? (
              <div className="p-8 text-center text-xs font-mono text-zinc-500">LOADING STREAMS...</div>
            ) : streams.length === 0 ? (
              <div className="p-12 text-center text-xs font-mono text-zinc-500">
                NO STREAMS REGISTERED YET. USE THE FORM TO CREATE ONE.
              </div>
            ) : (
              <div className="divide-y divide-zinc-800">
                {streams.map((st) => (
                  <div key={st.stream_id} className="p-5 flex items-center justify-between hover:bg-zinc-900/40 transition-colors">
                    <div className="space-y-1">
                      <div className="flex items-center gap-3">
                        <span className="font-mono text-sm font-bold text-zinc-100">{st.stream_id}</span>
                        <StatusBadge status={st.status} />
                      </div>
                      <p className="text-xs text-zinc-400">{st.description || "No description provided."}</p>
                      <span className="text-[11px] font-mono text-zinc-600 block">CREATED: {st.created_at}</span>
                    </div>

                    <Link
                      href={`/streams/${st.stream_id}`}
                      className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-mono rounded transition-colors flex items-center gap-1 shrink-0"
                    >
                      OPEN STREAM <ArrowRight className="w-3.5 h-3.5" />
                    </Link>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
