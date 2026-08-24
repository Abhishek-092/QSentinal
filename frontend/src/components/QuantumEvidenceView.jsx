import React, { useEffect, useState } from 'react';
import { Atom, RefreshCw } from 'lucide-react';
import { runSession } from '../api';
import QuantumSimPanel from './QuantumSimPanel';

function MetricBar({ label, value, max = 1, color = 'neon' }) {
  const pct = Math.min(100, (value / max) * 100);
  const colors = {
    neon: 'bg-neon',
    acid: 'bg-acid',
    ice: 'bg-ice',
    hot: 'bg-hot',
  };
  return (
    <div className="space-y-1">
      <div className="flex justify-between font-mono text-sm">
        <span className="text-dim">{label}</span>
        <span className="text-ink-fg">{typeof value === 'number' ? value.toFixed(4) : value}</span>
      </div>
      <div className="h-2 overflow-hidden border border-line bg-ink">
        <div className={`h-full ${colors[color] || colors.neon} transition-all`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function QuantumEvidenceView() {
  const [telemetry, setTelemetry] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [noiseP, setNoiseP] = useState(0.02);

  const fetchEvidence = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await runSession(`evidence-${Date.now().toString(36)}`, noiseP);
      setTelemetry(data.telemetry);
    } catch (e) {
      setError(e.message || 'API offline');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchEvidence(); }, []);

  const m = telemetry?.mismatch_rate ?? 0;
  const c = telemetry?.correlation ?? 0;
  const h = telemetry?.entropy ?? 0;
  const pauli = telemetry?.pauli_consistency ?? 0;
  const f = telemetry?.fidelity ?? (1 - m);

  return (
    <div className="space-y-6">
      <div className="hacker-box border border-neon/20 bg-panel p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-heading">
              <Atom size={20} className="text-neon" /> Quantum evidence (from the statevector)
            </h2>
            <p className="text-sm text-dim">
              F = ⟨ψ|ρ_B|ψ⟩, s_a = 1−F, ⟨Z₁Z₂⟩ Bell correlator, S(ρ_B) = −Tr(ρ log₂ ρ).
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="font-mono text-xs text-dim">
              p={noiseP.toFixed(3)}
              <input
                type="range"
                min="0"
                max="0.3"
                step="0.01"
                value={noiseP}
                onChange={(e) => setNoiseP(Number(e.target.value))}
                className="ml-2 align-middle"
              />
            </label>
            <button
              onClick={fetchEvidence}
              disabled={loading}
              className="hacker-box-subtle flex items-center gap-2 border border-line bg-ink px-4 py-2 text-sm text-ink-fg hover:border-neon/50 hover:text-neon disabled:opacity-50"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Simulate
            </button>
          </div>
        </div>
        {error && <p className="mt-3 font-mono text-sm text-hot">{error}</p>}
      </div>

      {telemetry && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="hacker-box space-y-5 border border-neon/20 bg-panel p-6">
            <MetricBar label="Fidelity F = ⟨ψ|ρ_B|ψ⟩" value={f} max={1} color={f > 0.9 ? 'neon' : f > 0.7 ? 'acid' : 'hot'} />
            <MetricBar label="Infidelity / mismatch s_a = 1−F" value={m} max={0.5} color={m > 0.12 ? 'hot' : m > 0.05 ? 'acid' : 'neon'} />
            <MetricBar label="Bell correlator ⟨Z₁Z₂⟩" value={(c + 1) / 2} max={1} color="ice" />
            <MetricBar label="Von Neumann entropy S(ρ_B)" value={h} max={1} color="acid" />
            <MetricBar label="Pauli Bloch consistency (1+n·n̂)/2" value={pauli} max={1} color={pauli > 0.7 ? 'neon' : 'hot'} />
          </div>
          <QuantumSimPanel snapshot={telemetry} title="Same session, live observables" />
        </div>
      )}
    </div>
  );
}
