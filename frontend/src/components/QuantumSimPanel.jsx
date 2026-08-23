import React from 'react';

function BlochPlane({ label, vector }) {
  const x = Number(vector?.x ?? 0);
  const z = Number(vector?.z ?? 0);
  const cx = 70 + x * 52;
  const cy = 70 - z * 52;
  return (
    <div className="hacker-box-subtle border border-line bg-ink p-3">
      <div className="mb-2 font-mono text-[11px] text-dim">{label}</div>
      <svg viewBox="0 0 140 140" className="h-36 w-full">
        <circle cx="70" cy="70" r="52" fill="none" stroke="var(--color-line)" />
        <line x1="18" y1="70" x2="122" y2="70" stroke="var(--color-line)" strokeWidth="1" />
        <line x1="70" y1="18" x2="70" y2="122" stroke="var(--color-line)" strokeWidth="1" />
        <text x="126" y="74" fill="var(--color-dim)" fontSize="10">x</text>
        <text x="74" y="16" fill="var(--color-dim)" fontSize="10">z</text>
        <line x1="70" y1="70" x2={cx} y2={cy} stroke="var(--color-neon)" strokeWidth="2" />
        <circle cx={cx} cy={cy} r="5" fill="var(--color-neon)" />
      </svg>
      <div className="mt-1 font-mono text-[11px] text-dim">
        n=({x.toFixed(2)}, {Number(vector?.y ?? 0).toFixed(2)}, {z.toFixed(2)})
      </div>
    </div>
  );
}

export default function QuantumSimPanel({ snapshot, title = 'Live statevector' }) {
  if (!snapshot) {
    return (
      <div className="hacker-box border border-neon/20 bg-panel p-6 text-sm text-dim">
        Run a session to stream the 3-qubit statevector, Bloch vectors, and QS-L statistics.
      </div>
    );
  }

  const amps = snapshot.amplitudes || [];
  const fid = Number(snapshot.fidelity ?? 1 - (snapshot.mismatch_rate ?? 0));

  return (
    <div className="hacker-box space-y-4 border border-neon/20 bg-panel p-6">
      <div>
        <h3 className="font-display font-semibold text-heading">{title}</h3>
        <p className="mt-1 font-mono text-xs text-neon">{snapshot.note || snapshot.phase || 'quantum snapshot'}</p>
      </div>
      <div className="grid grid-cols-2 gap-3 font-mono text-xs md:grid-cols-4">
        <div className="hacker-box-subtle border border-line bg-ink p-2">F = {fid.toFixed(4)}</div>
        <div className="hacker-box-subtle border border-line bg-ink p-2">s_a = {Number(snapshot.mismatch_rate ?? snapshot.s_a ?? 0).toFixed(4)}</div>
        <div className="hacker-box-subtle border border-line bg-ink p-2">⟨Z₁Z₂⟩ = {Number(snapshot.correlation ?? 0).toFixed(3)}</div>
        <div className="hacker-box-subtle border border-line bg-ink p-2">S(ρ_B) = {Number(snapshot.entropy ?? 0).toFixed(3)} bits</div>
      </div>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <BlochPlane label="Authorized |ψ⟩ Bloch (x–z)" vector={snapshot.bloch_message} />
        <BlochPlane label="Bob reconstructed Bloch (x–z)" vector={snapshot.bloch_bob} />
      </div>
      <div>
        <div className="mb-2 font-mono text-[11px] text-dim">P(|q0 q1 q2⟩)</div>
        <div className="space-y-1">
          {amps.map((row) => (
            <div key={row.ket} className="flex items-center gap-2 font-mono text-[11px]">
              <span className="w-14 text-dim">{row.ket}</span>
              <div className="h-2 flex-1 overflow-hidden border border-line bg-ink">
                <div className="h-full bg-neon" style={{ width: `${Math.min(100, row.p * 100)}%` }} />
              </div>
              <span className="w-16 text-right text-dim">{row.p.toFixed(3)}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
