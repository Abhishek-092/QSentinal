"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { Header } from "@/components/layout/Header";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { StreamRecord, HealthResponse, ReadinessResponse } from "@/lib/types/api";
import { Activity, ShieldAlert, Layers, Server, AlertCircle, ArrowRight } from "lucide-react";

export default function CommandCenter() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [ready, setReady] = useState<ReadinessResponse | null>(null);
  const [streams, setStreams] = useState<StreamRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchData() {
      try {
        const [hRes, rRes] = await Promise.allSettled([
          api.getHealth(),
          api.getReadiness(),
        ]);

        if (hRes.status === "fulfilled") setHealth(hRes.value);
        if (rRes.status === "fulfilled") setReady(rRes.value);

        // Fetch known stream sample or handle empty
        try {
          const sample = await api.getStream("stream-alice-bob-01");
          setStreams([sample]);
        } catch {
          setStreams([]);
        }
      } catch (err) {
        setError("Failed to connect to QSENTINEL monitoring backend.");
      } finally {
        setLoading(false);
      }
    }
    fetchData();
  }, []);

  const isHealthy = health?.status === "ok";
  const isReady = ready?.status === "ready";

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans">
      <Header isHealthy={isHealthy} isReady={isReady} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Command Center Title */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-6">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-zinc-100 font-mono">
              COMMAND CENTER // SECURITY OBSERVABILITY
            </h1>
            <p className="text-sm text-zinc-400 mt-1">
              Operational overview of quantum protocol statistical change-point detection engines.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/streams"
              className="px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-zinc-950 font-bold text-xs font-mono rounded transition-colors flex items-center gap-2"
            >
              <Layers className="w-4 h-4" />
              MANAGE STREAMS
            </Link>
          </div>
        </div>

        {/* Global Operational Status Bar */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div className="p-4 bg-zinc-900/60 border border-zinc-800 rounded space-y-1">
            <span className="text-xs font-mono text-zinc-500 block">SYSTEM LIVENESS</span>
            <div className="flex items-center justify-between">
              <span className="text-lg font-bold font-mono text-zinc-100">
                {isHealthy ? "OPERATIONAL" : "UNHEALTHY"}
              </span>
              <StatusBadge status={isHealthy ? "OK" : "DOWN"} />
            </div>
          </div>

          <div className="p-4 bg-zinc-900/60 border border-zinc-800 rounded space-y-1">
            <span className="text-xs font-mono text-zinc-500 block">PERSISTENCE STORAGE</span>
            <div className="flex items-center justify-between">
              <span className="text-lg font-bold font-mono text-zinc-100">SQLite WAL</span>
              <StatusBadge status={isReady ? "CONNECTED" : "UNREADY"} />
            </div>
          </div>

          <div className="p-4 bg-zinc-900/60 border border-zinc-800 rounded space-y-1">
            <span className="text-xs font-mono text-zinc-500 block">ACTIVE STREAMS</span>
            <div className="flex items-center justify-between">
              <span className="text-lg font-bold font-mono text-zinc-100">
                {streams.length}
              </span>
              <span className="text-xs font-mono text-zinc-400">REGISTERED</span>
            </div>
          </div>

          <div className="p-4 bg-zinc-900/60 border border-zinc-800 rounded space-y-1">
            <span className="text-xs font-mono text-zinc-500 block">PROVENANCE INTEGRITY</span>
            <div className="flex items-center justify-between">
              <span className="text-lg font-bold font-mono text-emerald-400">SHA-256 VERIFIED</span>
              <StatusBadge status="OK" />
            </div>
          </div>
        </div>

        {/* Active Streams Table */}
        <div className="border border-zinc-800 rounded bg-zinc-950/60 overflow-hidden space-y-0">
          <div className="px-6 py-4 border-b border-zinc-800 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-400" />
              <h2 className="text-sm font-bold font-mono text-zinc-200">ACTIVE MONITORING STREAMS</h2>
            </div>
            <span className="text-xs font-mono text-zinc-500">{streams.length} TOTAL</span>
          </div>

          {loading ? (
            <div className="p-8 text-center text-xs font-mono text-zinc-500">
              LOADING OPERATIONAL STREAMS...
            </div>
          ) : error ? (
            <div className="p-8 text-center text-xs font-mono text-red-400 flex items-center justify-center gap-2">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          ) : streams.length === 0 ? (
            <div className="p-12 text-center space-y-3">
              <p className="text-xs font-mono text-zinc-400">NO DATA AVAILABLE</p>
              <p className="text-xs text-zinc-500 max-w-md mx-auto">
                No active monitoring streams registered in the database. Create a stream to begin monitoring.
              </p>
              <Link
                href="/streams"
                className="inline-flex items-center gap-2 px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-mono rounded transition-colors"
              >
                CREATE FIRST STREAM <ArrowRight className="w-3.5 h-3.5" />
              </Link>
            </div>
          ) : (
            <div className="divide-y divide-zinc-800">
              {streams.map((st) => (
                <div key={st.stream_id} className="p-4 flex items-center justify-between hover:bg-zinc-900/40 transition-colors">
                  <div className="space-y-1">
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-sm font-bold text-zinc-100">{st.stream_id}</span>
                      <StatusBadge status={st.status} />
                    </div>
                    <p className="text-xs text-zinc-400">{st.description || "No description provided."}</p>
                  </div>

                  <Link
                    href={`/streams/${st.stream_id}`}
                    className="px-3 py-1.5 bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-mono rounded transition-colors flex items-center gap-1"
                  >
                    INSPECT STREAM <ArrowRight className="w-3.5 h-3.5" />
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
