"use client";

import { useState } from "react";
import { ChevronDown, ChevronRight, Lock, Key } from "lucide-react";
import { ProvenanceBundle } from "@/lib/types/api";

export function ProvenanceSection({ provenance }: { provenance?: ProvenanceBundle | null }) {
  const [isOpen, setIsOpen] = useState(false);

  if (!provenance) {
    return (
      <div className="p-4 border border-zinc-800 rounded bg-zinc-950/50 text-xs font-mono text-zinc-500">
        NO PROVENANCE BUNDLE ATTACHED
      </div>
    );
  }

  return (
    <div className="border border-zinc-800 rounded bg-zinc-950/50 overflow-hidden">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full px-4 py-3 flex items-center justify-between text-left text-xs font-mono hover:bg-zinc-900/50 transition-colors"
      >
        <div className="flex items-center gap-2 text-zinc-300">
          <Lock className="w-4 h-4 text-emerald-400" />
          <span>CRYPTOGRAPHIC PROVENANCE BUNDLE</span>
          <span className="text-zinc-500">({provenance.architecture_version})</span>
        </div>
        <div className="flex items-center gap-1 text-zinc-500">
          {isOpen ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </div>
      </button>

      {isOpen && (
        <div className="px-4 pb-4 border-t border-zinc-800/60 pt-3 font-mono text-xs space-y-2.5">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="p-2.5 bg-zinc-900/60 border border-zinc-800 rounded">
              <span className="text-zinc-500 block mb-1">STAGE 1 ARTIFACT HASH:</span>
              <span className="text-zinc-300 break-all">
                {provenance.stage1_artifact_hash || "UNBOUND"}
              </span>
            </div>

            <div className="p-2.5 bg-zinc-900/60 border border-zinc-800 rounded">
              <span className="text-zinc-500 block mb-1">STAGE 2 ARTIFACT HASH:</span>
              <span className="text-zinc-300 break-all">
                {provenance.stage2_artifact_hash || "UNBOUND"}
              </span>
            </div>

            <div className="p-2.5 bg-zinc-900/60 border border-zinc-800 rounded">
              <span className="text-zinc-500 block mb-1">CHANGE-POINT ARTIFACT HASH:</span>
              <span className="text-zinc-300 break-all">
                {provenance.changepoint_artifact_hash || "UNBOUND"}
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
