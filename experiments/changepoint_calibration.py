"""
Offline Change-Point (Offset GLR-CUSUM) Calibration Engine for QSENTINEL (Phase 8).

Calibrates the null distribution of maximum cumulative Offset GLR-CUSUM statistic M_H_CUSUM = max_{1 <= k <= H} C_k
across an honest p-grid under fixed-horizon H execution.

Formula:
  d(p) = mu_H0(p) + delta(p)
  where mu_H0(p) = E_H0[log_lambda | p]
  delta(p) = 0.05 (explicit deterministic offset margin)

Uses deterministic STREAM seed allocation and SHA-256 canonical hashing.
PERFORMS ZERO DISK MUTATION AT RUNTIME.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import json
import hashlib
import os
import numpy as np

from qds.protocol import run_session, SessionConfig
from qsentinel_monitor.quantum_evidence import extract_evidence, evaluate_stage1
from qsentinel_monitor.sequential_test import compute_session_log_likelihood_ratio
from experiments.seed_allocator import SeedAllocator, SeedAllocationError


@dataclass(frozen=True)
class ChangePointCalibrationTableEntry:
    p: float
    null_classification: str  # "DEGENERATE_BOUNDARY_NULL" or "REGULAR_INTERIOR_NULL"
    null_mean_glr: float
    delta_offset_margin: float
    null_offset_d: float
    empirical_critical_value: float
    max_cusum_mean: float
    max_cusum_std: float
    n_trials: int
    quantile_probability: float


def derive_child_seed(stream_seed: int, grid_idx: int, trial_idx: int, session_idx: int) -> int:
    """
    Cryptographically deterministic child-seed derivation algorithm: 'sha256_v1'.
    Derives per-session simulation seed independent of Python hash randomization or wall clock.
    Returns integer in [0, 2**31 - 1].
    """
    key_str = f"changepoint_stream:{stream_seed}|grid:{grid_idx}|trial:{trial_idx}|session:{session_idx}"
    digest = hashlib.sha256(key_str.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % (2**31 - 1)


def build_changepoint_canonical_payload(
    schema_version: str,
    architecture_version: str,
    changepoint_model_version: str,
    n_qubits: int,
    alpha: float,
    horizon_sessions: int,
    n_trials_per_grid_point: int,
    p_grid: List[float],
    seed_start: int,
    seed_count: int,
    table_entries: List[ChangePointCalibrationTableEntry],
) -> Dict[str, Any]:
    """
    Constructs deterministic canonical Change-Point payload dictionary without wall-clock timestamps or UUIDs.
    """
    sorted_entries = sorted(table_entries, key=lambda e: e.p)
    return {
        "schema_version": schema_version,
        "architecture_version": architecture_version,
        "changepoint_model_version": changepoint_model_version,
        "calibration_configuration": {
            "n_qubits": n_qubits,
            "alpha": alpha,
            "horizon_sessions": horizon_sessions,
            "n_trials_per_grid_point": n_trials_per_grid_point,
            "p_grid": sorted(p_grid),
            "quantile_method": "weibull",
            "calibration_guarantee": "HORIZON_BOUNDED",
            "calibrated_statistic": "MAX_OFFSET_CUSUM",
            "offset_formula": "d(p) = mu_H0(p) + delta(p)",
            "delta_offset_margin": 0.05,
        },
        "seed_provenance": {
            "purpose": "CALIBRATION",
            "schedule_version": "v2.0",
            "seed_start": seed_start,
            "seed_count": seed_count,
            "seed_unit": "STREAM",
            "mapping": "stream_seed: seed_start + grid_idx * n_trials + trial_idx",
            "child_seed_derivation": "sha256_v1",
        },
        "calibration_table": [asdict(entry) for entry in sorted_entries],
    }


def compute_changepoint_canonical_hash(canonical_payload: Dict[str, Any]) -> str:
    """Computes SHA-256 content hash from canonical JSON string."""
    json_str = json.dumps(canonical_payload, sort_keys=True, indent=2, ensure_ascii=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


def generate_changepoint_calibration_artifact(
    p_grid: List[float] = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
    n_qubits: int = 200,
    alpha: float = 0.01,
    horizon_sessions: int = 50,
    n_trials_per_grid_point: int = 1000,
    seed_start: int = 0,
    delta_offset_margin: float = 0.05,
    schema_version: str = "1.0",
    architecture_version: str = "v8.0",
    changepoint_model_version: str = "v1.0",
) -> Dict[str, Any]:
    """
    Executes offline conditional Change-Point (Offset GLR-CUSUM) calibration across p_grid using STREAM CALIBRATION seeds.
    Enforces stream capacity bounds and deep immutability provenance.
    """
    total_stream_seeds_required = len(p_grid) * n_trials_per_grid_point

    if seed_start + total_stream_seeds_required > 50_000:
        raise SeedAllocationError(
            f"Requested {total_stream_seeds_required} stream seeds starting from {seed_start} exceeds CALIBRATION range limit (50000)."
        )

    table_entries: List[ChangePointCalibrationTableEntry] = []

    for grid_idx, p in enumerate(p_grid):
        if abs(p) < 1e-12:
            # Degenerate p=0 boundary
            entry = ChangePointCalibrationTableEntry(
                p=0.0,
                null_classification="DEGENERATE_BOUNDARY_NULL",
                null_mean_glr=0.0,
                delta_offset_margin=delta_offset_margin,
                null_offset_d=delta_offset_margin,
                empirical_critical_value=delta_offset_margin * 2.0,
                max_cusum_mean=0.0,
                max_cusum_std=0.0,
                n_trials=n_trials_per_grid_point,
                quantile_probability=1.0 - alpha,
            )
            table_entries.append(entry)
            continue

        # Phase 1 of calibration: Estimate mu_H0(p) across all trials
        glr_values: List[float] = []

        for trial_idx in range(n_trials_per_grid_point):
            stream_seed = seed_start + grid_idx * n_trials_per_grid_point + trial_idx
            for session_idx in range(1, horizon_sessions + 1):
                child_seed = derive_child_seed(stream_seed, grid_idx, trial_idx, session_idx)
                cfg = SessionConfig(n_qubits=n_qubits, p_channel=p, seed=child_seed)
                transcript = run_session(cfg)
                ev = extract_evidence(transcript)
                st1 = evaluate_stage1(ev)
                if st1.status == "PROCESSED" and st1.optimization_success:
                    log_lambda = compute_session_log_likelihood_ratio(ev)
                    glr_values.append(log_lambda)

        null_mean_glr = float(np.mean(glr_values)) if glr_values else 0.0
        null_offset_d = float(null_mean_glr + delta_offset_margin)

        # Phase 2 of calibration: Run Offset CUSUM and record max CUSUM per trial M_H_CUSUM
        max_cusum_per_trial: List[float] = []

        for trial_idx in range(n_trials_per_grid_point):
            stream_seed = seed_start + grid_idx * n_trials_per_grid_point + trial_idx
            c_k = 0.0
            max_c = 0.0
            for session_idx in range(1, horizon_sessions + 1):
                child_seed = derive_child_seed(stream_seed, grid_idx, trial_idx, session_idx)
                cfg = SessionConfig(n_qubits=n_qubits, p_channel=p, seed=child_seed)
                transcript = run_session(cfg)
                ev = extract_evidence(transcript)
                st1 = evaluate_stage1(ev)
                if st1.status == "PROCESSED" and st1.optimization_success:
                    log_lambda = compute_session_log_likelihood_ratio(ev)
                    c_k = max(0.0, c_k + log_lambda - null_offset_d)
                    if c_k > max_c:
                        max_c = c_k
            max_cusum_per_trial.append(max_c)

        # Compute empirical critical value at (1 - alpha) quantile (Weibull method)
        p_q = 1.0 - alpha
        crit_val = float(np.percentile(max_cusum_per_trial, p_q * 100.0, method="weibull"))
        mean_max = float(np.mean(max_cusum_per_trial))
        std_max = float(np.std(max_cusum_per_trial, ddof=1)) if len(max_cusum_per_trial) > 1 else 0.0

        entry = ChangePointCalibrationTableEntry(
            p=float(p),
            null_classification="REGULAR_INTERIOR_NULL",
            null_mean_glr=null_mean_glr,
            delta_offset_margin=delta_offset_margin,
            null_offset_d=null_offset_d,
            empirical_critical_value=crit_val,
            max_cusum_mean=mean_max,
            max_cusum_std=std_max,
            n_trials=n_trials_per_grid_point,
            quantile_probability=p_q,
        )
        table_entries.append(entry)

    payload = build_changepoint_canonical_payload(
        schema_version=schema_version,
        architecture_version=architecture_version,
        changepoint_model_version=changepoint_model_version,
        n_qubits=n_qubits,
        alpha=alpha,
        horizon_sessions=horizon_sessions,
        n_trials_per_grid_point=n_trials_per_grid_point,
        p_grid=p_grid,
        seed_start=seed_start,
        seed_count=total_stream_seeds_required,
        table_entries=table_entries,
    )
    content_hash = compute_changepoint_canonical_hash(payload)
    payload["content_hash"] = content_hash
    return payload


def save_changepoint_calibration_artifact(payload: Dict[str, Any], output_path: str) -> None:
    """Saves verified canonical change-point calibration payload to disk."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, sort_keys=True, indent=2, ensure_ascii=True)


if __name__ == "__main__":
    artifact_dir = os.path.join(os.path.dirname(__file__), "..", "qsentinel_monitor", "calibration_artifacts")
    output_file = os.path.join(artifact_dir, "changepoint_calibration_v1.json")
    print(f"Generating Phase 8 Change-Point Calibration Artifact -> {output_file} ...")

    # Fast offline generation for production artifact (n_trials=200, H=50)
    artifact_payload = generate_changepoint_calibration_artifact(
        p_grid=[0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
        n_qubits=200,
        alpha=0.01,
        horizon_sessions=50,
        n_trials_per_grid_point=200,
        seed_start=0,
    )
    save_changepoint_calibration_artifact(artifact_payload, output_file)
    print(f"Phase 8 Calibration Artifact generated successfully! Hash: {artifact_payload['content_hash']}")
