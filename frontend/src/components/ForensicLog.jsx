import React, { useEffect, useState } from 'react';
import { Shield, RefreshCw, CheckCircle2, XCircle } from 'lucide-react';
import { getForensicLog, verifyForensicChain } from '../api';

export default function ForensicLog() {
  const [entries, setEntries] = useState([]);
  const [verification, setVerification] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const [logData, verifyData] = await Promise.all([
        getForensicLog(100),
        verifyForensicChain(),
      ]);
      setEntries(logData.entries || []);
      setVerification(verifyData);
    } catch (e) {
      setError(e.message || 'API offline');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleVerify = async () => {
    setError('');
    try {
      setVerification(await verifyForensicChain());
    } catch (e) {
      setError(e.message || 'Verify failed');
    }
  };

  return (
    <div className="space-y-6">
      <div className="hacker-box border border-neon/20 bg-panel p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="flex items-center gap-2 font-display text-lg font-semibold text-heading">
              <Shield size={20} className="text-neon" /> Forensic Audit Log
            </h2>
            <p className="text-sm text-dim">Append-only SHA-256 hash chain with Ed25519 signatures.</p>
          </div>
          <div className="flex gap-3">
            <button
              onClick={handleVerify}
              className="hacker-box-subtle flex items-center gap-2 bg-neon px-4 py-2 font-display text-sm font-bold text-ink hover:bg-acid"
            >
              {verification?.valid ? <CheckCircle2 size={16} /> : <Shield size={16} />}
              Verify Chain
            </button>
            <button
              onClick={load}
              disabled={loading}
              className="hacker-box-subtle flex items-center gap-2 border border-line bg-ink px-4 py-2 text-sm text-ink-fg hover:border-neon/50 hover:text-neon disabled:opacity-50"
            >
              <RefreshCw size={16} className={loading ? 'animate-spin' : ''} /> Refresh
            </button>
          </div>
        </div>
        {error && <p className="mt-3 font-mono text-sm text-hot">{error}</p>}
      </div>

      {verification && (
        <div className={`hacker-box flex items-center gap-3 border p-4 ${
          verification.valid
            ? 'border-neon/40 bg-ink text-neon'
            : 'border-hot/40 bg-ink text-hot'
        }`}
        >
          {verification.valid ? <CheckCircle2 size={20} /> : <XCircle size={20} />}
          <div className="font-mono text-sm">
            <span className="font-bold">{verification.valid ? 'INTEGRITY OK' : 'CHAIN BROKEN'}</span>
            {' — '}{verification.details} ({verification.entries} entries)
          </div>
        </div>
      )}

      <div className="hacker-box overflow-hidden border border-neon/20 bg-panel">
        <div className="max-h-[28rem] overflow-y-auto overflow-x-auto">
          <table className="w-full font-mono text-sm">
            <thead className="sticky top-0 bg-ink">
              <tr className="text-left text-dim">
                <th className="px-4 py-3">Timestamp</th>
                <th className="px-4 py-3">Session</th>
                <th className="px-4 py-3">Protocol</th>
                <th className="px-4 py-3">Advisory</th>
                <th className="px-4 py-3">Hash</th>
              </tr>
            </thead>
            <tbody>
              {entries.length === 0 && (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-dim">No log entries yet</td></tr>
              )}
              {[...entries].reverse().map((e, i) => (
                <tr key={i} className="hacker-box-subtle border-t border-line hover:bg-neon/5">
                  <td className="px-4 py-2 text-dim">{e.timestamp?.slice(0, 19)}</td>
                  <td className="px-4 py-2 text-ink-fg">{e.session_id}</td>
                  <td className={`px-4 py-2 ${e.protocol_accepted ? 'text-neon' : 'text-hot'}`}>
                    {e.protocol_accepted ? 'ACCEPT' : 'REJECT'}
                  </td>
                  <td className="px-4 py-2 text-acid">{e.monitoring_verdict}</td>
                  <td className="max-w-[8rem] truncate px-4 py-2 text-dim">{e.entry_hash?.slice(0, 12)}…</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
