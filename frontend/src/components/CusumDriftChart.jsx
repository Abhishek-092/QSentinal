import React, { useEffect, useMemo, useState } from 'react';
import { TrendingUp, RefreshCw } from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine,
} from 'recharts';
import { getCusumHistory, runSession } from '../api';
import { useTheme } from '../ThemeContext';

const THRESHOLD = 2.0;

export default function CusumDriftChart() {
  const { theme } = useTheme();
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const chartColors = useMemo(() => {
    if (typeof window === 'undefined') {
      return { grid: '#163d28', axis: '#7ea88c', line: '#00ff9c', hot: '#ff3864', panel: '#07140e', fg: '#e7ffef' };
    }
    const root = getComputedStyle(document.documentElement);
    return {
      grid: root.getPropertyValue('--color-line').trim(),
      axis: root.getPropertyValue('--color-dim').trim(),
      line: root.getPropertyValue('--color-neon').trim(),
      hot: root.getPropertyValue('--color-hot').trim(),
      panel: root.getPropertyValue('--color-panel').trim(),
      fg: root.getPropertyValue('--color-fg').trim(),
    };
  }, [theme]);

  const loadHistory = async () => {
    try {
      const { history } = await getCusumHistory(50);
      setData(history.length ? history : [{ session: 1, cusum: 0 }]);
    } catch (e) {
      setError(e.message || 'API offline');
    }
  };

  const ingestSession = async () => {
    setLoading(true);
    setError('');
    try {
      await runSession(`cusum-seed-${Date.now().toString(36)}`, 0.035);
      await loadHistory();
    } catch (e) {
      setError(e.message || 'Failed to ingest session');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadHistory();
  }, []);

  return (
    <div className="space-y-6">
      <div className="hacker-box border border-neon/20 bg-panel p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-heading">
              <TrendingUp size={20} className="text-neon" /> Cross-Session Drift Tracking (GLR-CUSUM)
            </h2>
            <p className="text-sm text-dim">Unconditional session ingestion monitoring low-and-slow cumulative bias.</p>
          </div>
          <button
            onClick={ingestSession}
            disabled={loading}
            className="hacker-box-subtle flex items-center gap-2 border border-line bg-ink px-4 py-2 text-sm text-ink-fg hover:border-neon/50 hover:text-neon disabled:opacity-50"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Ingest Session
          </button>
        </div>
        {error && <p className="mt-3 font-mono text-sm text-hot">{error}</p>}
      </div>

      <div className="hacker-box border border-neon/20 bg-panel p-6">
        <div className="h-72 w-full pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
              <XAxis dataKey="session" stroke={chartColors.axis} label={{ value: 'Session #', position: 'insideBottom', offset: -5, fill: chartColors.axis }} />
              <YAxis stroke={chartColors.axis} label={{ value: 'CUSUM', angle: -90, position: 'insideLeft', fill: chartColors.axis }} />
              <Tooltip contentStyle={{ backgroundColor: chartColors.panel, borderColor: chartColors.grid, color: chartColors.fg }} />
              <ReferenceLine y={THRESHOLD} stroke={chartColors.hot} strokeDasharray="5 5" label={{ value: 'Threshold', fill: chartColors.hot, fontSize: 11 }} />
              <Line type="monotone" dataKey="cusum" stroke={chartColors.line} strokeWidth={2} dot={{ fill: chartColors.line, r: 3 }} activeDot={{ r: 5 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
