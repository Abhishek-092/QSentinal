import React from "react";
import { ShieldAlert, AlertTriangle, Info, CheckCircle2, ShieldX } from "lucide-react";

interface StatusBadgeProps {
  status: string;
  type?: "posture" | "severity" | "epoch" | "detector";
}

export function StatusBadge({ status, type = "posture" }: StatusBadgeProps) {
  let colorClasses = "bg-zinc-800 text-zinc-300 border-zinc-700";
  let icon = <Info className="w-3.5 h-3.5 inline mr-1" />;

  const s = status.toUpperCase();

  if (s === "NOMINAL" || s === "ACTIVE" || s === "INFORMATIONAL" || s === "OK" || s === "CHANGEPOINT_CALIBRATED_NOMINAL" || s === "STAGE2_CALIBRATED_NOMINAL") {
    colorClasses = "bg-emerald-500/10 text-emerald-400 border-emerald-500/30";
    icon = <CheckCircle2 className="w-3.5 h-3.5 inline mr-1" />;
  } else if (s === "ELEVATED_STAGE1" || s === "LOW" || s === "MEDIUM") {
    colorClasses = "bg-yellow-500/10 text-yellow-400 border-yellow-500/30";
    icon = <AlertTriangle className="w-3.5 h-3.5 inline mr-1" />;
  } else if (s.includes("ELEVATED") || s === "HIGH" || s === "CRITICAL" || s === "ELEVATED_CRITICAL") {
    colorClasses = "bg-red-500/10 text-red-400 border-red-500/30";
    icon = <ShieldAlert className="w-3.5 h-3.5 inline mr-1" />;
  } else if (s.includes("EXPIRED") || s === "CLOSED" || s === "DETECTOR_HORIZON_EXCEEDED") {
    colorClasses = "bg-amber-500/10 text-amber-400 border-amber-500/30";
    icon = <AlertTriangle className="w-3.5 h-3.5 inline mr-1" />;
  } else if (s.includes("INTEGRITY") || s.includes("FAILURE") || s.includes("MISMATCH")) {
    colorClasses = "bg-rose-900/40 text-rose-300 border-rose-600 animate-pulse";
    icon = <ShieldX className="w-3.5 h-3.5 inline mr-1" />;
  }

  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded text-xs font-mono border ${colorClasses}`}>
      {icon}
      {status}
    </span>
  );
}
