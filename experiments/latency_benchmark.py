"""
Detection Latency Benchmark for QSENTINEL.

Measures how many sessions it takes for the CUSUM detector to flag a persistent
low-and-slow attack at various magnitudes.

Blueprint references: §5, §13 (GLR-CUSUM), §16, §23 Phase 12.
"""
from __future__ import annotations

import numpy as np
from typing import Any

from qds.protocol import run_session
from qsentinel_monitor.quantum_evidence.collector import extract_evidence
from qsentinel_monitor.glr_cusum import GLRCusumMonitor


def measure_detection_latency(
    attack_magnitude: float = 0.025,
    max_sessions: int = 200,
    base_noise_p: float = 0.02,
    n_qubits: int = 200,
    n_repeats: int = 10,
) -> dict[str, Any]:
    """
    Run repeated streams of attack sessions and measure how many sessions
    it takes for CUSUM to flag drift.

    Returns:
    - mean_detection_latency (sessions)
    - std_detection_latency
    - detection_rate (fraction of repeats that detected within max_sessions)
    """
    detection_latencies = []

    for r in range(n_repeats):
        cusum = GLRCusumMonitor()
        detected = False
        latency = max_sessions

        for t in range(max_sessions):
            seed = r * 10000 + t + 300_000
            transcript = run_session(
                f"lat-{seed}",
                noise_p=base_noise_p + attack_magnitude,
                attack="low_and_slow_drift",
                n_qubits=n_qubits,
                seed=seed,
            )

            evidence = extract_evidence(transcript)
            update = cusum.update(transcript.session_id, evidence.overall_mismatch_rate)

            if update.drift_detected:
                detected = True
                latency = t + 1
                break

        detection_latencies.append({
            "detected": detected,
            "latency": latency,
        })

    detected_count = sum(1 for d in detection_latencies if d["detected"])
    latencies = [d["latency"] for d in detection_latencies if d["detected"]]

    return {
        "attack_magnitude": attack_magnitude,
        "base_noise_p": base_noise_p,
        "max_sessions": max_sessions,
        "n_repeats": n_repeats,
        "detection_rate": detected_count / n_repeats,
        "mean_latency": float(np.mean(latencies)) if latencies else float(max_sessions),
        "std_latency": float(np.std(latencies)) if latencies else 0.0,
        "min_latency": min(latencies) if latencies else max_sessions,
        "max_latency": max(latencies) if latencies else max_sessions,
    }


def run_latency_sweep(
    magnitudes: tuple[float, ...] = (0.005, 0.01, 0.015, 0.02, 0.025, 0.03, 0.05),
    max_sessions: int = 200,
    n_repeats: int = 10,
) -> dict[float, dict[str, Any]]:
    """Run detection latency measurement across multiple attack magnitudes."""
    results = {}
    for mag in magnitudes:
        results[mag] = measure_detection_latency(
            attack_magnitude=mag,
            max_sessions=max_sessions,
            n_repeats=n_repeats,
        )
    return results


def format_latency_table(results: dict[float, dict[str, Any]]) -> str:
    """Format latency sweep as a readable table."""
    lines = []
    lines.append("Detection Latency Sweep — Low-and-Slow Attack Magnitudes")
    lines.append("=" * 80)
    lines.append(f"{'Magnitude':>10} {'Detect%':>9} {'Mean Lat':>10} {'Std Lat':>10} {'Min':>6} {'Max':>6}")
    lines.append("-" * 80)

    for mag, r in sorted(results.items()):
        lines.append(
            f"{mag:>10.4f} "
            f"{r['detection_rate']:>9.2%} "
            f"{r['mean_latency']:>10.1f} "
            f"{r['std_latency']:>10.1f} "
            f"{r['min_latency']:>6.0f} "
            f"{r['max_latency']:>6.0f}"
        )

    return "\n".join(lines)
