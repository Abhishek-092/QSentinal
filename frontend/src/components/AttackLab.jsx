import React, { useEffect, useState } from 'react';
import { FileCheck, Activity, Zap } from 'lucide-react';
import { getAttackStrategies, runAttack, runSession } from '../api';
import QuantumSimPanel from './QuantumSimPanel';

export default function AttackLab() {
  const [strategies, setStrategies] = useState([]);
  const [selected, setSelected] = useState('');
  const [sessionResult, setSessionResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    getAttackStrategies()
      .then((d) => {
        setStrategies(d.strategies || []);
        if (d.strategies?.length) setSelected(d.strategies[0]);
      })
      .catch((e) => setError(e.message || 'Failed to load strategies — is the API running?'));
  }, []);

  const exec = async (fn) => {
    setLoading(true);
    setError('');
    try {
      setSessionResult(await fn());
    } catch (e) {
      setError(e.message || 'Simulation failed');
    } finally {
      setLoading(false);
    }
  };

  const protocol = sessionResult?.protocol_decision;
  const monitor = sessionResult?.monitoring_decision;
  const snap = sessionResult?.telemetry;

  return (
    <div className="space-y-6">
      <div className="hacker-box border border-neon/20 bg-panel p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="font-display text-lg font-semibold text-heading">Attack channel laboratory</h2>
          </div>
          <div className="flex flex-wrap gap-3">
            <select
              value={selected}
              onChange={(e) => setSelected(e.target.value)}
              className="border border-line bg-ink px-3 py-2 text-sm text-ink-fg"
            >
              {strategies.map((s) => (
                <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>
              ))}
            </select>
            <button
              onClick={() => exec(() => runAttack(selected, `atk-${Date.now().toString(36)}`))}
              disabled={loading || !selected}
              className="flex items-center gap-2 bg-hot px-4 py-2 font-display text-sm font-bold text-white hover:brightness-110 disabled:opacity-50"
            >
              <Zap size={16} /> Run attack
            </button>
            <button
              onClick={() => exec(() => runSession(`sess-${Date.now().toString(36)}`))}
              disabled={loading}
              className="bg-neon px-6 py-2.5 font-display font-bold text-ink shadow-neon hover:bg-acid disabled:opacity-50"
            >
              {loading ? 'Simulating...' : 'Honest session'}
            </button>
          </div>
        </div>
        {error && <p className="mt-4 font-mono text-sm text-hot">{error}</p>}
      </div>

      <QuantumSimPanel snapshot={snap} title="Reconstructed recipient state after the chosen channel" />

      {sessionResult && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="hacker-box relative border-2 border-solid border-neon/50 bg-panel p-6">
            <div className="absolute right-4 top-4 border border-neon/40 px-2 py-1 text-xs font-mono uppercase tracking-widest text-neon">
              Authoritative lane
            </div>
            <h3 className="mb-2 flex items-center gap-2 font-display text-lg font-bold text-neon">
              <FileCheck size={20} /> Protocol decision
            </h3>
            <div className="mt-4 space-y-3 font-mono text-sm">
              <div className="flex justify-between border-b border-line py-1">
                <span className="text-dim">Status:</span>
                <span className={protocol?.accepted ? 'font-bold text-neon' : 'font-bold text-hot'}>
                  {protocol?.accepted ? 'ACCEPTED' : 'REJECTED'}
                </span>
              </div>
              <div className="flex justify-between gap-4 border-b border-line py-1">
                <span className="text-dim">QS-L:</span>
                <span className="text-right text-ink-muted">{protocol?.reason}</span>
              </div>
              <div className="flex justify-between border-b border-line py-1">
                <span className="text-dim">Fidelity F:</span>
                <span className="text-ink-muted">{Number(snap?.fidelity ?? 0).toFixed(4)}</span>
              </div>
            </div>
          </div>

          <div className="hacker-box relative border-2 border-dashed border-acid/50 bg-panel p-6">
            <div className="absolute right-4 top-4 border border-acid/40 px-2 py-1 text-xs font-mono uppercase tracking-widest text-acid">
              Advisory watcher
            </div>
            <h3 className="mb-2 flex items-center gap-2 font-display text-lg font-bold text-acid">
              <Activity size={20} /> QSENTINEL monitor
            </h3>
            <div className="mt-4 space-y-3 font-mono text-sm">
              <div className="flex justify-between border-b border-line py-1">
                <span className="text-dim">Verdict:</span>
                <span className="font-bold text-acid">{monitor?.verdict}</span>
              </div>
              <div className="flex justify-between gap-4 border-b border-line py-1">
                <span className="text-dim">Details:</span>
                <span className="text-right text-ink-muted">{monitor?.details}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
