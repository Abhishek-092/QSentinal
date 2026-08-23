const API = '/api';

async function request(path, options) {
  const res = await fetch(`${API}${path}`, options);
  if (!res.ok) {
    const detail = await res.text().catch(() => '');
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

export async function getHealth() {
  return request('/health');
}

export async function runSession(sessionId, noiseP = 0.02, theta = 0.7853981633974483) {
  return request('/sessions/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId, noise_p: noiseP, theta }),
  });
}

export async function runAttack(strategy, sessionId) {
  return request('/attacks/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ strategy, session_id: sessionId }),
  });
}

export async function getAttackStrategies() {
  return request('/attacks/strategies');
}

export async function getCusumHistory(limit = 50) {
  return request(`/cusum/history?limit=${limit}`);
}

export async function getForensicLog(limit = 100) {
  return request(`/forensics/log?limit=${limit}`);
}

export async function verifyForensicChain() {
  return request('/forensics/verify');
}

export function streamSession(sessionId, onProgress, onComplete, onError, opts = {}) {
  const noiseP = opts.noiseP ?? 0.02;
  const theta = opts.theta ?? 0.7853981633974483;
  const qs = new URLSearchParams({ noise_p: String(noiseP), theta: String(theta) });
  const source = new EventSource(`${API}/sessions/${encodeURIComponent(sessionId)}/stream?${qs}`);
  let settled = false;

  const finish = (fn, payload) => {
    if (settled) return;
    settled = true;
    source.close();
    fn(payload);
  };

  source.addEventListener('progress', (e) => onProgress(JSON.parse(e.data)));
  source.addEventListener('complete', (e) => finish(onComplete, JSON.parse(e.data)));
  source.onerror = () => {
    source.close();
    if (settled) return;
    onProgress?.({ step: 'SSE unavailable — running one-shot session', progress: 60 });
    runSession(sessionId, noiseP, theta)
      .then((data) => {
        onProgress?.({
          step: 'Finalizing protocol & advisory verdicts',
          progress: 100,
          snapshot: data.telemetry,
        });
        finish(onComplete, {
          session_id: data.session_id,
          accepted: data.protocol_decision.accepted,
          reason: data.protocol_decision.reason,
          verdict: data.monitoring_decision.verdict,
          details: data.monitoring_decision.details,
          telemetry: data.telemetry,
          snapshot: data.telemetry,
          monitoring: data.monitoring_decision,
        });
      })
      .catch((err) => {
        settled = true;
        onError?.(err.message || 'Cannot reach API. Start uvicorn on port 8001.');
      });
  };
  return source;
}
