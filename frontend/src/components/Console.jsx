import React, { useEffect, useState } from 'react';
import { ArrowLeft, Shield } from 'lucide-react';
import LiveSession from './LiveSession';
import AttackLab from './AttackLab';
import QuantumEvidenceView from './QuantumEvidenceView';
import CusumDriftChart from './CusumDriftChart';
import ForensicLog from './ForensicLog';
import ThemeToggle from './ThemeToggle';
import { getHealth } from '../api';

const TABS = [
  { id: 'live', label: 'LIVE' },
  { id: 'lab', label: 'LAB' },
  { id: 'evidence', label: 'EVIDENCE' },
  { id: 'drift', label: 'DRIFT' },
  { id: 'forensics', label: 'FORENSICS' },
];

export default function Console({ onExit }) {
  const [activeTab, setActiveTab] = useState('lab');
  const [apiOnline, setApiOnline] = useState(null);

  useEffect(() => {
    getHealth()
      .then(() => setApiOnline(true))
      .catch(() => setApiOnline(false));
  }, []);

  return (
    <div className="relative min-h-screen overflow-x-hidden bg-ink font-mono text-ink-fg">
      <div className="scanlines" />
      <div className="grid-bg pointer-events-none fixed inset-0 opacity-70" />

      <header className="relative z-20 border-b border-neon/20 bg-ink/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-5 py-4">
          <div className="flex flex-wrap items-center gap-3">
            <button
              type="button"
              onClick={onExit}
              className="hacker-box-subtle flex items-center gap-1.5 border border-neon/50 px-2 py-1 text-xs uppercase tracking-widest text-neon hover:bg-neon hover:text-ink"
            >
              <ArrowLeft size={14} /> HQ
            </button>
            <Shield className="text-neon" size={18} />
            <span className="font-display text-xl font-bold tracking-[0.28em] text-heading">QSENTINEL</span>
            <span className="border border-neon/40 px-2 py-0.5 text-[10px] uppercase tracking-widest text-neon">
              Attack Console
            </span>
            <span
              className={`border px-2 py-0.5 text-[10px] uppercase tracking-widest ${
                apiOnline === true
                  ? 'border-neon/60 text-neon'
                  : apiOnline === false
                    ? 'border-hot/60 text-hot'
                    : 'border-line text-dim'
              }`}
            >
              {apiOnline === true ? 'API ONLINE' : apiOnline === false ? 'API OFFLINE' : 'API …'}
            </span>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <ThemeToggle />
            <nav className="flex flex-wrap gap-2">
              {TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`hacker-box-subtle px-4 py-2 text-xs font-display font-semibold uppercase tracking-widest transition-colors ${
                    activeTab === tab.id
                      ? 'bg-neon text-ink shadow-neon'
                      : 'border border-line text-dim hover:border-neon/50 hover:text-neon'
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </nav>
          </div>
        </div>
      </header>

      <main className="relative z-10 mx-auto max-w-7xl p-6">
        {activeTab === 'live' && <LiveSession />}
        {activeTab === 'lab' && <AttackLab />}
        {activeTab === 'evidence' && <QuantumEvidenceView />}
        {activeTab === 'drift' && <CusumDriftChart />}
        {activeTab === 'forensics' && <ForensicLog />}
      </main>
    </div>
  );
}
