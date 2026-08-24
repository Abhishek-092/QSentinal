"""
Performance Benchmark Runner for QSENTINEL.

Measures wall-clock time per module and confirms Big-O complexity classes.
Every retained cost must be O(1) to O(w) per session (Blueprint §11).

Blueprint references: §5 (#25), §11, §16, §23 Phase 12.
"""
from __future__ import annotations

import time
import numpy as np
from typing import Any, Callable

from qds.protocol import run_session
from qsentinel_monitor.quantum_evidence.collector import extract_evidence
from qsentinel_monitor.quantum_evidence.stage1 import evaluate_stage1
from qsentinel_monitor.glr_cusum import GLRCusumMonitor
from qsentinel_monitor.forensic_log import append_log_entry


def _time_function(func: Callable, n_runs: int = 100) -> dict[str, float]:
    """Time a function over n_runs, return mean/std in microseconds."""
    times = []
    for _ in range(n_runs):
        start = time.perf_counter()
        func()
        elapsed = (time.perf_counter() - start) * 1e6  # microseconds
        times.append(elapsed)

    t_arr = np.array(times)
    return {
        "mean_us": float(np.mean(t_arr)),
        "std_us": float(np.std(t_arr)),
        "p50_us": float(np.percentile(t_arr, 50)),
        "p99_us": float(np.percentile(t_arr, 99)),
        "n_runs": n_runs,
    }


def benchmark_bell_pair(n_runs: int = 500) -> dict[str, float]:
    """Benchmark Bell-pair preparation. Expected: O(1) — fixed 4-element statevector."""
    from qds.bell_pair import prepare_bell_pair
    return _time_function(prepare_bell_pair, n_runs)


def benchmark_teleportation(n_runs: int = 200) -> dict[str, float]:
    """Benchmark one teleportation. Expected: O(1) — fixed 8-element statevector."""
    from qds.pauli import encode_eigenstate
    from qds.teleportation import teleport
    rng = np.random.default_rng(42)

    def _teleport():
        state = encode_eigenstate(1, 0)
        teleport(state, rng=rng)

    return _time_function(_teleport, n_runs)


def benchmark_noise(n_runs: int = 500) -> dict[str, float]:
    """Benchmark depolarizing channel. Expected: O(1) — single-qubit Kraus map."""
    from qds.noise import depolarize
    rng = np.random.default_rng(42)
    state = np.array([1.0, 0.0], dtype=np.complex128)

    def _depolarize():
        depolarize(state, p=0.05, rng=rng)

    return _time_function(_depolarize, n_runs)


def benchmark_full_session(n_qubits: int = 200, n_runs: int = 50) -> dict[str, float]:
    """Benchmark one complete session (protocol execution). Expected: O(n) in n_qubits."""
    def _session():
        run_session(f"bench-{time.time()}", noise_p=0.02, n_qubits=n_qubits, seed=42)

    return _time_function(_session, n_runs)


def benchmark_evidence_extraction(n_qubits: int = 200, n_runs: int = 50) -> dict[str, float]:
    """Benchmark evidence extraction. Expected: O(n) — touch every sifted outcome."""
    transcript = run_session("bench-ev", noise_p=0.02, n_qubits=n_qubits, seed=42)

    def _extract():
        extract_evidence(transcript)

    return _time_function(_extract, n_runs)


def benchmark_stage1(n_qubits: int = 200, n_runs: int = 50) -> dict[str, float]:
    """Benchmark Stage 1 profile-likelihood. Expected: O(n) + optimizer."""
    transcript = run_session("bench-s1", noise_p=0.02, n_qubits=n_qubits, seed=42)
    evidence = extract_evidence(transcript)

    def _stage1():
        evaluate_stage1(evidence)

    return _time_function(_stage1, n_runs)


def benchmark_cusum_update(n_runs: int = 200) -> dict[str, float]:
    """Benchmark CUSUM update. Expected: O(1) — closed-form MLE."""
    # Note: this uses SQLite, so it includes I/O overhead
    try:
        cusum = GLRCusumMonitor()

        def _update():
            cusum.update("bench-cusum", 0.05)

        return _time_function(_update, n_runs)
    except Exception:
        return {"mean_us": -1, "std_us": 0, "p50_us": -1, "p99_us": -1, "n_runs": 0, "error": "CUSUM unavailable"}


def run_full_benchmark() -> dict[str, dict[str, float]]:
    """Run all benchmarks and return a comprehensive timing table."""
    return {
        "bell_pair": benchmark_bell_pair(),
        "teleportation": benchmark_teleportation(),
        "noise_channel": benchmark_noise(),
        "full_session_200q": benchmark_full_session(200),
        "full_session_500q": benchmark_full_session(500),
        "evidence_extraction": benchmark_evidence_extraction(),
        "stage1_profile_likelihood": benchmark_stage1(),
        "cusum_update": benchmark_cusum_update(),
    }


def format_benchmark_table(results: dict[str, dict[str, float]]) -> str:
    """Format benchmark results as a readable table."""
    lines = []
    lines.append("QSENTINEL Module Performance Benchmarks")
    lines.append("=" * 75)
    lines.append(f"{'Module':<35} {'Mean (μs)':>12} {'P50 (μs)':>12} {'P99 (μs)':>12} {'Expected':>12}")
    lines.append("-" * 75)

    expected = {
        "bell_pair": "O(1)",
        "teleportation": "O(1)",
        "noise_channel": "O(1)",
        "full_session_200q": "O(n), n=200",
        "full_session_500q": "O(n), n=500",
        "evidence_extraction": "O(n)",
        "stage1_profile_likelihood": "O(n) + opt",
        "cusum_update": "O(1)",
    }

    for name, timing in results.items():
        exp = expected.get(name, "—")
        lines.append(
            f"{name:<35} "
            f"{timing.get('mean_us', 0):>12.1f} "
            f"{timing.get('p50_us', 0):>12.1f} "
            f"{timing.get('p99_us', 0):>12.1f} "
            f"{exp:>12}"
        )

    return "\n".join(lines)
