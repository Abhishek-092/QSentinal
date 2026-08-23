"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { api } from "@/lib/api/client";
import { Header } from "@/components/layout/Header";
import { StatusBadge } from "@/components/ui/StatusBadge";
import { ProvenanceSection } from "@/components/monitoring/ProvenanceSection";
import { SessionSubmissionForm } from "@/components/monitoring/SessionSubmissionForm";
import { EpochRenewalModal } from "@/components/monitoring/EpochRenewalModal";
import {
  EpochRecord,
  MonitoringStateResponse,
  UnifiedThreatAssessment,
  UnifiedMonitoringResult,
  ApiError,
} from "@/lib/types/api";
import { Shield, Activity, ArrowLeft, RefreshCw, AlertTriangle, CheckCircle2, Lock } from "lucide-react";

export default function EpochConsolePage({ params }: { params: Promise<{ streamId: string; epochId: string }> }) {
  const resolvedParams = use(params);
  const { streamId, epochId } = resolvedParams;

  const [epoch, setEpoch] = useState<EpochRecord | null>(null);
  const [state, setState] = useState<MonitoringStateResponse | null>(null);
  const [assessment, setAssessment] = useState<UnifiedThreatAssessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);

  const loadConsoleData = async () => {
    try {
      const [epRes, stRes] = await Promise.all([
        api.getEpoch(streamId, epochId),
        api.getEpochState(streamId, epochId),
      ]);
      setEpoch(epRes);
      setState(stRes);

      // Attempt loading latest assessment if available
      try {
        const ta = await api.getLatestAssessment(streamId, epochId);
        setAssessment(ta);
      } catch {
        setAssessment(null);
      }
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        setError({ code: err.code, message: err.message });
      } else {
        setError({ code: "CONNECTION_FAILURE", message: "Failed to connect to monitoring backend." });
      }
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadConsoleData();
  }, [streamId, epochId]);

  const handleSessionProcessed = (res: UnifiedMonitoringResult) => {
    setAssessment(res.threat_assessment);
    loadConsoleData();
  };

  const handleEpochRenewed = (newEpoch: EpochRecord) => {
    setEpoch(newEpoch);
    loadConsoleData();
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 font-mono flex items-center justify-center p-4">
        <div className="flex items-center gap-3">
          <RefreshCw className="w-5 h-5 animate-spin text-emerald-400" />
          <span>LOADING MONITORING CONSOLE [{epochId}]...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans">
        <Header isHealthy={false} isReady={false} />
        <main className="max-w-4xl mx-auto px-4 py-16 text-center space-y-4">
          <div className="p-4 bg-red-500/10 border border-red-500/30 text-red-400 rounded-lg font-mono inline-block">
            <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
            <h2 className="text-base font-bold">[{error.code}] SECURITY CONSOLE ERROR</h2>
            <p className="text-xs text-red-300 mt-1">{error.message}</p>
          </div>
          <div>
            <Link href={`/streams/${streamId}`} className="text-xs font-mono text-zinc-400 hover:text-zinc-200 underline">
              ← Return to Stream {streamId}
            </Link>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-zinc-950 text-zinc-100 font-sans">
      <Header isHealthy={true} isReady={true} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8">
        {/* Console Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b border-zinc-800 pb-6">
          <div className="flex items-center gap-4">
            <Link href={`/streams/${streamId}`} className="p-2 bg-zinc-900 border border-zinc-800 rounded text-zinc-400 hover:text-zinc-200">
              <ArrowLeft className="w-4 h-4" />
            </Link>
            <div>
              <div className="flex items-center gap-3">
                <span className="text-xs font-mono text-zinc-500">STREAM: {streamId}</span>
                <span className="text-zinc-600">/</span>
                <span className="text-sm font-mono font-bold text-zinc-100">{epochId}</span>
                {epoch && <StatusBadge status={epoch.status} />}
              </div>
              <h1 className="text-xl font-bold tracking-tight text-zinc-100 font-mono mt-1">
                SECURITY MONITORING CONSOLE // EPOCH #{epoch?.epoch_index}
              </h1>
            </div>
          </div>

          <div className="flex items-center gap-3">
            {epoch && (
              <EpochRenewalModal streamId={streamId} epochId={epochId} onEpochRenewed={handleEpochRenewed} />
            )}
          </div>
        </div>

        {/* Security Posture & Threat Severity Banner */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="p-5 bg-zinc-950 border border-zinc-800 rounded space-y-2">
            <span className="text-xs font-mono text-zinc-500 block">AUTHORITATIVE SECURITY POSTURE</span>
            <div className="flex items-center gap-3 pt-1">
              <StatusBadge status={assessment?.security_posture || "NOMINAL"} />
            </div>
          </div>

          <div className="p-5 bg-zinc-950 border border-zinc-800 rounded space-y-2">
            <span className="text-xs font-mono text-zinc-500 block">THREAT SEVERITY LEVEL</span>
            <div className="flex items-center gap-3 pt-1">
              <StatusBadge status={assessment?.threat_severity || "INFORMATIONAL"} />
            </div>
          </div>

          <div className="p-5 bg-zinc-950 border border-zinc-800 rounded space-y-2">
            <span className="text-xs font-mono text-zinc-500 block">SEQUENCE PROGRESS ($k / H$)</span>
            <div className="font-mono text-lg font-bold text-zinc-100 pt-1">
              SESSION #{state?.sequence_number || 0}
            </div>
          </div>
        </div>

        {/* Threat Assessment Detailed Block */}
        <div className="p-6 bg-zinc-950 border border-zinc-800 rounded space-y-4">
          <div className="flex items-center justify-between border-b border-zinc-800 pb-3">
            <div className="flex items-center gap-2">
              <Shield className="w-4 h-4 text-emerald-400" />
              <h2 className="text-sm font-bold font-mono text-zinc-200">SYNTHESIZED THREAT ASSESSMENT</h2>
            </div>
            <span className="text-xs font-mono text-zinc-500">AUTHORITATIVE</span>
          </div>

          {assessment ? (
            <div className="space-y-4 font-mono text-xs">
              <div className="p-3 bg-zinc-900/60 border border-zinc-800 rounded text-zinc-300">
                <span className="text-zinc-500 block mb-1">EXPLANATION:</span>
                {assessment.explanation}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="p-3 bg-zinc-900/60 border border-zinc-800 rounded">
                  <span className="text-zinc-500 block mb-1">CONTRIBUTING DETECTORS:</span>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {assessment.contributing_detectors.length > 0 ? (
                      assessment.contributing_detectors.map((d) => (
                        <span key={d} className="px-2 py-0.5 bg-red-500/10 border border-red-500/30 text-red-400 rounded text-[11px]">
                          {d}
                        </span>
                      ))
                    ) : (
                      <span className="text-emerald-400">NONE (NOMINAL EXECUTION)</span>
                    )}
                  </div>
                </div>

                <div className="p-3 bg-zinc-900/60 border border-zinc-800 rounded">
                  <span className="text-zinc-500 block mb-1">ESTIMATED EXCURSION ONSET ($\hat{\tau}$):</span>
                  <span className="text-zinc-200 font-bold">
                    {assessment.estimated_excursion_onset !== null
                      ? `SESSION #${assessment.estimated_excursion_onset}`
                      : "NONE DETECTED"}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="p-8 text-center text-xs font-mono text-zinc-500">
              NO THREAT ASSESSMENT RECORDED YET FOR THIS EPOCH. TRANSMIT A SESSION TO BEGIN MONITORING.
            </div>
          )}
        </div>

        {/* Detector Status Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {/* Stage 2 Sequential Evidence Engine */}
          <div className="p-5 bg-zinc-950 border border-zinc-800 rounded space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
              <span className="font-bold text-zinc-200">STAGE 2 SEQUENTIAL GLR ENGINE</span>
              <StatusBadge status={state?.stage2_decision_status || "UNINITIALIZED"} />
            </div>

            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-zinc-500">PROCESSED VALID COUNT:</span>
                <span className="text-zinc-200">{state?.stage2_processed_count || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">CUMULATIVE GLR EVIDENCE ($S_k$):</span>
                <span className="text-emerald-400 font-bold">
                  {state?.stage2_cumulative_glr !== undefined
                    ? state.stage2_cumulative_glr.toFixed(4)
                    : "0.0000"}
                </span>
              </div>
            </div>
          </div>

          {/* Change-Point (Offset GLR-CUSUM) Engine */}
          <div className="p-5 bg-zinc-950 border border-zinc-800 rounded space-y-3 font-mono text-xs">
            <div className="flex items-center justify-between border-b border-zinc-800 pb-2">
              <span className="font-bold text-zinc-200">OFFSET GLR-CUSUM CHANGE-POINT</span>
              <StatusBadge status={state?.changepoint_decision_status || "UNINITIALIZED"} />
            </div>

            <div className="space-y-2">
              <div className="flex justify-between">
                <span className="text-zinc-500">CUSUM STATISTIC ($C_k$):</span>
                <span className="text-emerald-400 font-bold">
                  {state?.changepoint_cusum_statistic !== undefined
                    ? state.changepoint_cusum_statistic.toFixed(4)
                    : "0.0000"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">ACTIVE RUN LENGTH ($N_k$):</span>
                <span className="text-zinc-200">{state?.changepoint_active_run_length || 0}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">ESTIMATED EXCURSION ONSET ($\hat{\tau}$):</span>
                <span className="text-zinc-200">
                  {state?.changepoint_estimated_onset !== null && state?.changepoint_estimated_onset !== undefined
                    ? `SESSION #${state.changepoint_estimated_onset}`
                    : "N/A"}
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Session Submission Form */}
        <SessionSubmissionForm streamId={streamId} epochId={epochId} onSessionProcessed={handleSessionProcessed} />

        {/* Cryptographic Provenance Section */}
        <ProvenanceSection provenance={assessment?.provenance_bundle} />
      </main>
    </div>
  );
}
