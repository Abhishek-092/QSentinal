import React, { useEffect, useRef, useState } from 'react';
import {
  ArrowRight,
  Cpu,
  Eye,
  Radio,
  Shield,
  Terminal,
  Zap,
} from 'lucide-react';
import ThemeToggle from './ThemeToggle';
import { useTheme } from '../ThemeContext';

const LOGS = [
  '> init QDS register |q0 q1 q2⟩',
  '> distribute |Φ+⟩ on sender/recipient EPR',
  '> encode R_y(θ)|0⟩  θ=0.785 rad',
  '> channel E(ρ)=(1-p)ρ+(p/3)Σσρσ',
  '> teleport + Pauli X^m1 Z^m0',
  '> QS-L check  s_a = 1−F  ≶  0.12',
  '> verdict: ACCEPT  F=0.9871',
  '> forensic hash chained  ed25519',
];

const FEATURES = [
  {
    icon: Radio,
    title: 'Live teleportation',
    body: 'Stream a real 3-qubit density matrix through Bell pair, encoding, noise, and Bennett teleportation — every stage, live.',
  },
  {
    icon: Zap,
    title: 'Attack laboratory',
    body: 'Run intercept-resend, replay, basis spoof, and more. Each attack changes the channel; QS-L scores the damage.',
  },
  {
    icon: Eye,
    title: 'Quantum evidence',
    body: 'Read fidelity, Bell correlation, entropy, and Bloch vectors straight from the reconstructed state — not placeholders.',
  },
];

const STEPS = [
  { n: '01', t: 'Bell pair', d: 'H on sender EPR, CNOT onto recipient. |Φ+⟩ = (|00⟩+|11⟩)/√2.' },
  { n: '02', t: 'Encode', d: 'Authorized message |ψ(θ)⟩ = R_y(θ)|0⟩ on qubit 0.' },
  { n: '03', t: 'Channel', d: 'Depolarizing Kraus map plus optional adversarial intercept.' },
  { n: '04', t: 'Teleport', d: 'CNOT·H, Z-measure, recipient applies X^{m1} Z^{m0}.' },
  { n: '05', t: 'QS-L', d: 'Accept iff s_a < 0.12 and Pauli Bloch consistency holds.' },
];

const ATTACKS = [
  ['intercept_resend', 'Collapse sender EPR in Z'],
  ['basis_spoof', 'X-basis intercept on the Bell half'],
  ['replay', 'No fresh EPR — product state only'],
  ['impersonation', 'Swap |1⟩ for authorized |ψ(θ)⟩'],
  ['unauthorized_verification', 'Skip recipient Pauli correction'],
  ['channel_manipulation', 'Heavy depolarizing on the link'],
  ['clean_forgery', 'Forge |0⟩ instead of R_y(θ)|0⟩'],
  ['entanglement_probe', 'Extra CNOT from recipient onto sender'],
];

function MatrixRain() {
  const ref = useRef(null);
  const { theme } = useTheme();

  useEffect(() => {
    const canvas = ref.current;
    if (!canvas) return undefined;
    const ctx = canvas.getContext('2d');
    let frame;
    const glyphs = '01ΦΨλθρ⟨⟩⊕⊗QSENTINEL';
    const resize = () => {
      canvas.width = canvas.offsetWidth;
      canvas.height = canvas.offsetHeight;
    };
    resize();
    const cols = () => Math.max(8, Math.floor(canvas.width / 16));
    let drops = Array(cols()).fill(1);
    const draw = () => {
      const root = getComputedStyle(document.documentElement);
      ctx.fillStyle = root.getPropertyValue('--matrix-fade').trim();
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.fillStyle = root.getPropertyValue('--matrix-glyph').trim();
      ctx.font = '13px "Share Tech Mono", monospace';
      const n = cols();
      if (drops.length !== n) drops = Array(n).fill(1);
      drops.forEach((y, i) => {
        const ch = glyphs[Math.floor(Math.random() * glyphs.length)];
        ctx.fillText(ch, i * 16, y * 16);
        drops[i] = y * 16 > canvas.height && Math.random() > 0.975 ? 0 : y + 1;
      });
      frame = requestAnimationFrame(draw);
    };
    frame = requestAnimationFrame(draw);
    window.addEventListener('resize', resize);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener('resize', resize);
    };
  }, [theme]);

  return <canvas ref={ref} className="absolute inset-0 h-full w-full opacity-40" />;
}

function TypeLine() {
  const full = 'quantum digital signature · threat surface · live simulation';
  const [text, setText] = useState('');
  useEffect(() => {
    let i = 0;
    const id = setInterval(() => {
      i += 1;
      setText(full.slice(0, i));
      if (i >= full.length) clearInterval(id);
    }, 28);
    return () => clearInterval(id);
  }, []);
  return (
    <p className="text-sm tracking-wide text-neon md:text-base">
      {text}
      <span className="cursor-blink">█</span>
    </p>
  );
}

function TerminalPane() {
  const [n, setN] = useState(1);
  useEffect(() => {
    const id = setInterval(() => setN((v) => (v % LOGS.length) + 1), 900);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="hacker-box live-ring overflow-hidden border border-neon/40 bg-ink/90 shadow-neon">
      <div className="flex items-center gap-2 border-b border-neon/20 bg-panel px-3 py-2">
        <span className="h-2.5 w-2.5 rounded-full bg-hot" />
        <span className="h-2.5 w-2.5 rounded-full bg-acid" />
        <span className="h-2.5 w-2.5 rounded-full bg-neon" />
        <span className="ml-2 text-xs text-dim">root@qsentinel:~ /qds/session</span>
      </div>
      <div className="h-64 space-y-1.5 p-4 font-mono text-sm">
        {LOGS.slice(0, n).map((line) => (
          <div key={line} className="text-neon/90">
            {line}
          </div>
        ))}
        <div className="cursor-blink text-acid">_</div>
      </div>
    </div>
  );
}

export default function Landing({ onEnterLab }) {
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-ink font-mono text-ink-fg">
      <div className="scanlines" />
      <div className="grid-bg pointer-events-none fixed inset-0 opacity-70" />

      <header className="relative z-20 border-b border-neon/20 bg-ink/80 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div className="flex items-center gap-3">
            <Shield className="text-neon" size={22} />
            <span className="font-display text-xl font-bold tracking-[0.28em] text-heading">QSENTINEL</span>
            <span className="border border-neon/40 px-2 py-0.5 text-[10px] uppercase tracking-widest text-neon">
              QDS Monitor
            </span>
          </div>
          <nav className="flex flex-wrap items-center gap-4 text-xs uppercase tracking-widest text-dim">
            <a href="#features" className="hover:text-neon">Features</a>
            <a href="#protocol" className="hover:text-neon">Protocol</a>
            <a href="#attacks" className="hover:text-neon">Attacks</a>
            <a href="#mission" className="hover:text-neon">Mission</a>
            <ThemeToggle />
            <button
              type="button"
              onClick={onEnterLab}
              className="bg-neon px-4 py-2 font-bold text-ink transition-colors hover:bg-acid"
            >
              Enter lab →
            </button>
          </nav>
        </div>
      </header>

      <section className="relative z-10 mx-auto grid max-w-6xl items-center gap-12 px-5 pb-20 pt-14 lg:grid-cols-2">
        <div className="absolute inset-0 -z-10 overflow-hidden">
          <MatrixRain />
        </div>
        <div className="space-y-6">
          <p className="text-xs uppercase tracking-[0.4em] text-acid">Access node · live simulation</p>
          <h1 className="glitch font-display text-4xl font-bold leading-tight text-heading md:text-6xl">
            Break the
            <br />
            <span className="text-neon">quantum signature.</span>
            <br />
            Watch it hold.
          </h1>
          <TypeLine />
          <p className="max-w-xl text-base leading-relaxed text-ink-muted md:text-lg">
            QSENTINEL is a runtime monitor for a 3-qubit quantum digital signature.
            Simulate honest teleportation, fire real channel attacks, and read QS-L
            fidelity — live, from the density matrix.
          </p>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={onEnterLab}
              className="hacker-box-subtle flex items-center gap-2 bg-neon px-6 py-3 font-display text-lg font-bold text-ink shadow-neon hover:bg-acid"
            >
              Launch attack console <ArrowRight size={18} />
            </button>
            <a
              href="#protocol"
              className="hacker-box-subtle border border-neon/50 px-6 py-3 font-display font-semibold text-neon hover:bg-neon/10"
            >
              Read the circuit
            </a>
          </div>
        </div>
        <TerminalPane />
      </section>

      <section className="relative z-10 border-y border-neon/20 bg-panel/80">
        <div className="mx-auto grid max-w-6xl grid-cols-2 gap-6 px-5 py-8 text-center md:grid-cols-4">
          {[
            ['3', 'qubit QDS register'],
            ['10', 'physical attack profiles'],
            ['0.12', 'QS-L infidelity gate'],
            ['LIVE', 'statevector + ρ map'],
          ].map(([k, v]) => (
            <div key={v} className="hacker-box hacker-box-subtle border border-line bg-panel/50 p-4">
              <div className="font-display text-3xl text-acid">{k}</div>
              <div className="mt-1 text-xs uppercase tracking-widest text-dim">{v}</div>
            </div>
          ))}
        </div>
      </section>

      <section id="features" className="relative z-10 mx-auto max-w-6xl px-5 py-20">
        <p className="mb-3 text-xs uppercase tracking-[0.35em] text-neon">Capabilities</p>
        <h2 className="mb-4 font-display text-3xl font-bold text-heading md:text-4xl">
          What the console actually does
        </h2>
        <p className="mb-12 max-w-2xl text-base leading-relaxed text-ink-muted">
          Three core tools — simulate the protocol, attack the channel, and read the evidence.
        </p>
        <div className="grid gap-6 md:grid-cols-3">
          {FEATURES.map((f, i) => (
            <article
              key={f.title}
              className="hacker-box group flex flex-col border border-line bg-panel p-7 hover:border-neon/50"
            >
              <div className="mb-5 flex h-11 w-11 items-center justify-center border border-neon/30 bg-ink text-neon transition-colors group-hover:border-neon group-hover:bg-neon/10">
                <f.icon size={22} strokeWidth={1.75} />
              </div>
              <p className="mb-2 font-mono text-[11px] uppercase tracking-[0.25em] text-dim">
                0{i + 1}
              </p>
              <h3 className="mb-3 font-display text-xl font-semibold text-heading">{f.title}</h3>
              <p className="text-[15px] leading-relaxed text-ink-muted">{f.body}</p>
            </article>
          ))}
        </div>
      </section>

      <section id="protocol" className="relative z-10 border-y border-neon/15 bg-panel/60">
        <div className="mx-auto max-w-6xl px-5 py-20">
          <p className="mb-3 text-xs uppercase tracking-[0.4em] text-acid">Circuit</p>
          <h2 className="mb-10 font-display text-3xl text-heading md:text-4xl">How a session is scored</h2>
          <div className="grid gap-4 md:grid-cols-5">
            {STEPS.map((s) => (
              <div key={s.n} className="hacker-box hacker-box-subtle border border-line border-l-2 border-l-neon bg-panel/40 p-4 pl-4">
                <div className="font-display text-2xl text-acid">{s.n}</div>
                <div className="mt-1 font-display text-heading">{s.t}</div>
                <p className="mt-2 text-xs leading-relaxed text-dim">{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section id="attacks" className="relative z-10 mx-auto max-w-6xl px-5 py-20">
        <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="mb-3 text-xs uppercase tracking-[0.4em] text-hot">Threat surface</p>
            <h2 className="font-display text-3xl text-heading md:text-4xl">Attacks you can run</h2>
          </div>
          <button
            type="button"
            onClick={onEnterLab}
            className="hacker-box-subtle border border-hot px-4 py-2 font-display font-semibold text-hot hover:bg-hot hover:text-white"
          >
            Open lab
          </button>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          {ATTACKS.map(([name, desc]) => (
            <div
              key={name}
              className="hacker-box flex items-start gap-3 border border-line bg-ink/60 px-4 py-3"
            >
              <Terminal size={16} className="mt-0.5 shrink-0 text-hot" />
              <div>
                <div className="text-sm text-neon">{name}</div>
                <div className="text-xs text-dim">{desc}</div>
              </div>
            </div>
          ))}
        </div>
      </section>

      <section id="mission" className="relative z-10 border-y border-neon/20 bg-gradient-to-r from-panel via-ink to-panel">
        <div className="mx-auto grid max-w-6xl items-center gap-10 px-5 py-20 lg:grid-cols-2">
          <div>
            <p className="mb-3 text-xs uppercase tracking-[0.4em] text-ice">Mission</p>
            <h2 className="mb-4 font-display text-3xl text-heading md:text-4xl">
              Catch the forgery, keep the physics
            </h2>
            <p className="mb-4 leading-relaxed text-ink-muted">
              Digital signatures on a quantum channel fail in ways classical dashboards
              cannot see. QSENTINEL sits beside the QDS protocol: it measures mismatch,
              entropy, and drift, then writes an advisory verdict without ever mutating
              ACCEPT / REJECT.
            </p>
            <ul className="space-y-2 text-sm text-dim">
              <li className="flex gap-2">
                <Cpu size={16} className="mt-0.5 text-neon" /> NumPy density-matrix core — no ML black box
              </li>
              <li className="flex gap-2">
                <Shield size={16} className="mt-0.5 text-neon" /> Monitor cannot override protocol decisions
              </li>
              <li className="flex gap-2">
                <Radio size={16} className="mt-0.5 text-neon" /> SSE stream of every circuit stage
              </li>
            </ul>
          </div>
          <div className="hacker-box border border-neon/40 bg-ink p-8 shadow-neon">
            <p className="mb-2 text-xs text-dim">READY FOR OPERATOR</p>
            <p className="mb-6 font-display text-2xl text-heading">
              Drop into the lab. Run an honest session. Then break the channel.
            </p>
            <button
              type="button"
              onClick={onEnterLab}
              className="hacker-box-subtle w-full bg-acid py-3 font-display text-lg font-bold text-ink hover:bg-neon"
            >
              ENTER ATTACK LAB
            </button>
          </div>
        </div>
      </section>

      <footer className="relative z-10 border-t border-neon/20">
        <div className="mx-auto flex max-w-6xl flex-wrap justify-between gap-4 px-5 py-8 text-xs text-dim">
          <span>QSENTINEL · quantum signature sentinel</span>
          <span>operator console · hash #lab</span>
        </div>
      </footer>
    </div>
  );
}
