"""
Offline Stage 2 Sequential Calibration Engine for QSENTINEL (Phase 6D).

Calibrates the null distribution of maximum cumulative sequential GLR evidence M_H = max_{1 <= k <= H} S_k
across an honest p-grid under fixed-horizon H execution.

Uses deterministic STREAM seed allocation and SHA-256 canonical hashing.
PERFORMS ZERO DISK MUTATION AT RUNTIME.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import json
import hashlib
import numpy as np

from qds.protocol import run_session, SessionConfig
from qsentinel_monitor.quantum_evidence import extract_evidence, evaluate_stage1
from qsentinel_monitor.sequential_test import compute_session_log_likelihood_ratio
from experiments.seed_allocator import SeedAllocator, SeedAllocationError


@dataclass(frozen=True)
class Stage2CalibrationTableEntry:
    p: float
    null_classification: str  # "DEGENERATE_BOUNDARY_NULL" or "REGULAR_INTERIOR_NULL"
    empirical_critical_value: float
    max_statistic_mean: float
    max_statistic_std: float
    n_trials: int
    quantile_probability: float


def derive_child_seed(stream_seed: int, grid_idx: int, trial_idx: int, session_idx: int) -> int:
    """
    Cryptographically deterministic child-seed derivation algorithm: 'sha256_v1'.
    Derives per-session simulation seed independent of Python hash randomization or wall clock.
    Returns integer in [0, 2**31 - 1].
    """
    key_str = f"stream:{stream_seed}|grid:{grid_idx}|trial:{trial_idx}|session:{session_idx}"
    digest = hashlib.sha256(key_str.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % (2**31 - 1)


def build_stage2_canonical_payload(
    schema_version: str,
    architecture_version: str,
    stage2_model_version: str,
    n_qubits: int,
    alpha: float,
    horizon_sessions: int,
    n_trials_per_grid_point: int,
    p_grid: List[float],
    seed_start: int,
    seed_count: int,
    table_entries: List[Stage2CalibrationTableEntry],
) -> Dict[str, Any]:
    """
    Constructs deterministic canonical Stage 2 payload dictionary without wall-clock timestamps or UUIDs.
    """
    sorted_entries = sorted(table_entries, key=lambda e: e.p)
    return {
        "schema_version": schema_version,
        "architecture_version": architecture_version,
        "stage2_model_version": stage2_model_version,
        "calibration_configuration": {
            "n_qubits": n_qubits,
            "alpha": alpha,
            "horizon_sessions": horizon_sessions,
            "n_trials_per_grid_point": n_trials_per_grid_point,
            "p_grid": sorted(p_grid),
            "quantile_method": "weibull",
            "calibration_guarantee": "HORIZON_BOUNDED",
            "calibrated_statistic": "MAX_CUMULATIVE_EVIDENCE",
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


def compute_stage2_canonical_hash(canonical_payload: Dict[str, Any]) -> str:
    """
    Computes SHA-256 content hash from canonical JSON string (sorted keys, indent 2, ascii).
    """
    json_str = json.dumps(canonical_payload, sort_keys=True, indent=2, ensure_ascii=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


def generate_stage2_calibration_artifact(
    p_grid: List[float] = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
    n_qubits: int = 200,
    alpha: float = 0.01,
    horizon_sessions: int = 50,
    n_trials_per_grid_point: int = 1000,
    seed_start: int = 0,
    schema_version: str = "1.0",
    architecture_version: str = "v6.0",
    stage2_model_version: str = "v1.0",
) -> Dict[str, Any]:
    """
    Executes offline conditional Stage 2 sequential calibration across p_grid using STREAM CALIBRATION seeds.
    Enforces stream capacity bounds (N_grid * N_trials <= 50,000) and deep immutability provenance.
    """
    total_stream_seeds_required = len(p_grid) * n_trials_per_grid_point

    # Stream seed capacity check against [0, 50_000) CALIBRATION range
    if seed_start + total_stream_seeds_required > 50_000:
        raise SeedAllocationError(
            f"Requested {total_stream_seeds_required} stream seeds starting from {seed_start} exceeds CALIBRATION range limit (50000)."
        )

    table_entries: List[Stage2CalibrationTableEntry] = []

    for g_idx, p_val in enumerate(p_grid):
        p_val_rounded = float(round(p_val, 4))
        
        M_H_trial_values: List[float] = []

        for t_idx in range(n_trials_per_grid_point):
            offset = g_idx * n_trials_per_grid_point + t_idx
            stream_seed = SeedAllocator.get_seed("CALIBRATION", seed_start + offset)

            cumulative_S_k = 0.0
            max_S_k = 0.0

            # Simulate H-session stream
            for s_idx in range(1, horizon_sessions + 1):
                session_seed = derive_child_seed(stream_seed, g_idx, t_idx, s_idx)
                config = SessionConfig(n_qubits=n_qubits, noise_parameter_p=p_val_rounded, seed=session_seed)
                transcript = run_session(config)
                evidence = extract_evidence(transcript)

                # Compute production session GLR log-likelihood ratio
                log_lambda = compute_session_log_likelihood_ratio(evidence)
                cumulative_S_k += log_lambda
                if cumulative_S_k > max_S_k:
                    max_S_k = cumulative_S_k

            M_H_trial_values.append(max_S_k)

        M_H_arr = np.array(M_H_trial_values, dtype=np.float64)
        emp_crit_val = float(np.quantile(M_H_arr, 1.0 - alpha, method="weibull"))
        mean_val = float(np.mean(M_H_arr))
        std_val = float(np.std(M_H_arr))

        # Check p=0 boundary classification
        null_class = "DEGENERATE_BOUNDARY_NULL" if (p_val_rounded == 0.0 and emp_crit_val == 0.0) else "REGULAR_INTERIOR_NULL"

        entry = Stage2CalibrationTableEntry(
            p=p_val_rounded,
            null_classification=null_class,
            empirical_critical_value=emp_crit_val,
            max_statistic_mean=mean_val,
            max_statistic_std=std_val,
            n_trials=n_trials_per_grid_point,
            quantile_probability=1.0 - alpha,
        )
        table_entries.append(entry)

    canonical_payload = build_stage2_canonical_payload(
        schema_version=schema_version,
        architecture_version=architecture_version,
        stage2_model_version=stage2_model_version,
        n_qubits=n_qubits,
        alpha=alpha,
        horizon_sessions=horizon_sessions,
        n_trials_per_grid_point=n_trials_per_grid_point,
        p_grid=p_grid,
        seed_start=seed_start,
        seed_count=total_stream_seeds_required,
        table_entries=table_entries,
    )

    content_hash = compute_stage2_canonical_hash(canonical_payload)
    artifact_dict = dict(canonical_payload)
    artifact_dict["content_hash"] = content_hash
    return artifact_dict
