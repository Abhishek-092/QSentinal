import React, { useEffect, useRef, useState } from 'react';
import { Cpu, Play, CheckCircle2, XCircle } from 'lucide-react';
import { streamSession } from '../api';
import QuantumSimPanel from './QuantumSimPanel';

export default function LiveSession() {
  const [sessionId, setSessionId] = useState(`sess-live-${Date.now().toString(36)}`);
  const [noiseP, setNoiseP] = useState(0.02);
  const [theta, setTheta] = useState(0.785);
  const [progress, setProgress] = useState(0);
  const [step, setStep] = useState('');
  const [snapshot, setSnapshot] = useState(null);
  const [result, setResult] = useState(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState('');
  const sourceRef = useRef(null);

  useEffect(() => () => sourceRef.current?.close(), []);

  const startSession = () => {
    sourceRef.current?.close();
    const id = `sess-live-${Date.now().toString(36)}`;
    setSessionId(id);
    setRunning(true);
    setProgress(0);
    setStep('Connecting to protocol engine...');
    setResult(null);
    setError('');
    setSnapshot(null);

    sourceRef.current = streamSession(
      id,
      ({ step: s, progress: p, snapshot: snap }) => {
        setStep(s);
        setProgress(p);
        if (snap) setSnapshot(snap);
      },
      (data) => {
        setResult(data);
        if (data.snapshot || data.telemetry) setSnapshot(data.snapshot || data.telemetry);
        setRunning(false);
      },
      (message) => {
        setError(message || 'API connection error — start the backend on port 8001');
        setRunning(false);
      },
      { noiseP, theta },
    );
  };

  return (
    <div className="space-y-6">
      <div className="hacker-box border border-neon/20 bg-panel p-6">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-heading">
              <Cpu size={20} className="text-neon" /> Live teleportation pipeline
            </h2>
            <p className="text-sm text-dim">
              Real 3-qubit statevector: Bell pair → R_y(θ) → depolarizing channel → Bennett teleportation → QS-L.
            </p>
          </div>
          <button
            onClick={startSession}
            disabled={running}
            className="flex items-center gap-2 bg-neon px-6 py-2.5 font-display font-bold text-ink shadow-neon hover:bg-acid disabled:opacity-50"
          >
            <Play size={16} /> {running ? 'Simulating...' : 'Run live simulation'}
          </button>
        </div>

        <div className="mb-5 grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
          <label className="block">
            <span className="font-mono text-dim">Channel noise p = {noiseP.toFixed(3)}</span>
            <input
              type="range"
              min="0"
              max="0.35"
              step="0.005"
              value={noiseP}
              onChange={(e) => setNoiseP(Number(e.target.value))}
              className="mt-2 w-full"
            />
          </label>
          <label className="block">
            <span className="font-mono text-dim">Message Bloch angle θ = {theta.toFixed(3)} rad</span>
            <input
              type="range"
              min="0"
              max={Math.PI.toFixed(3)}
              step="0.01"
              value={theta}
              onChange={(e) => setTheta(Number(e.target.value))}
              className="mt-2 w-full"
            />
          </label>
        </div>

        <div className="space-y-3">
          <div className="flex justify-between text-sm">
            <span className="font-mono text-dim">{sessionId}</span>
            <span className="font-mono text-neon">{progress}%</span>
          </div>
          <div className="h-3 overflow-hidden border border-line bg-ink">
            <div
              className="h-full bg-gradient-to-r from-neon to-acid transition-all duration-300"
              style={{ width: `${progress}%` }}
            />
          </div>
          {step && <p className="font-mono text-sm text-ink-muted">{step}</p>}
          {error && <p className="font-mono text-sm text-hot">{error}</p>}
        </div>
      </div>

      <QuantumSimPanel snapshot={snapshot} title="Real-time quantum state" />

      {result && (
        <div className="grid grid-cols-1 gap-6 md:grid-cols-2">
          <div className="hacker-box border-2 border-solid border-neon/50 bg-panel p-6">
            <h3 className="mb-3 flex items-center gap-2 font-display font-bold text-neon">
              {result.accepted ? <CheckCircle2 size={18} /> : <XCircle size={18} className="text-hot" />}
              Protocol: {result.accepted ? 'ACCEPTED' : 'REJECTED'}
            </h3>
            <p className="font-mono text-sm text-ink-muted">{result.reason}</p>
          </div>
          <div className="hacker-box border-2 border-dashed border-acid/50 bg-panel p-6">
            <h3 className="mb-3 font-display font-bold text-acid">Advisory: {result.verdict}</h3>
            <p className="font-mono text-sm text-ink-muted">{result.details}</p>
          </div>
        </div>
      )}
    </div>
  );
}
