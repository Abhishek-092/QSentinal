"""
Offline Calibration Engine for QSENTINEL (Phase 5).

Generates conditional calibration tables across an honest p-grid using CALIBRATION seeds.
Produces versioned, SHA-256 content-hashed calibration artifacts.
"""
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional
import json
import hashlib
import numpy as np
import scipy.stats as stats

from qds.protocol import run_session, SessionConfig
from qsentinel_monitor.quantum_evidence import extract_evidence, evaluate_stage1
from experiments.seed_allocator import SeedAllocator, SeedAllocationError


@dataclass(frozen=True)
class CalibrationTableEntry:
    p: float
    null_classification: str  # "DEGENERATE_BOUNDARY_NULL" or "REGULAR_INTERIOR_NULL"
    empirical_critical_value: float
    asymptotic_reference_applicability: str  # "NOT_REGULARLY_APPLICABLE" or "REGULAR_CHI2_DF1"
    asymptotic_critical_value: Optional[float]
    n_trials: int
    quantile_probability: float


def build_canonical_payload(
    schema_version: str,
    architecture_version: str,
    stage1_model_version: str,
    n_qubits: int,
    alpha: float,
    n_trials_per_grid_point: int,
    p_grid: List[float],
    seed_start: int,
    seed_count: int,
    table_entries: List[CalibrationTableEntry],
) -> Dict[str, Any]:
    """
    Constructs deterministic canonical payload dictionary without wall-clock timestamps or UUIDs.
    """
    sorted_entries = sorted(table_entries, key=lambda e: e.p)
    return {
        "schema_version": schema_version,
        "architecture_version": architecture_version,
        "stage1_model_version": stage1_model_version,
        "calibration_configuration": {
            "n_qubits": n_qubits,
            "alpha": alpha,
            "n_trials_per_grid_point": n_trials_per_grid_point,
            "p_grid": sorted(p_grid),
        },
        "seed_provenance": {
            "purpose": "CALIBRATION",
            "schedule_version": "v1.0",
            "seed_start": seed_start,
            "seed_count": seed_count,
            "mapping": "linear_grid_offset: seed_start + grid_idx * n_trials + trial_idx",
        },
        "calibration_table": [asdict(entry) for entry in sorted_entries],
    }


def compute_canonical_hash(canonical_payload: Dict[str, Any]) -> str:
    """
    Computes SHA-256 content hash from canonical JSON string (sorted keys, indent 2, ascii).
    """
    json_str = json.dumps(canonical_payload, sort_keys=True, indent=2, ensure_ascii=True)
    return hashlib.sha256(json_str.encode("utf-8")).hexdigest()


def generate_calibration_artifact(
    p_grid: List[float] = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
    n_qubits: int = 200,
    alpha: float = 0.01,
    n_trials_per_grid_point: int = 1000,
    seed_start: int = 0,
    schema_version: str = "1.0",
    architecture_version: str = "v5.0",
    stage1_model_version: str = "v1.0",
) -> Dict[str, Any]:
    """
    Executes offline conditional Stage 1 calibration across p_grid using CALIBRATION seeds.
    Enforces capacity bounds and deep immutability provenance.
    """
    total_seeds_required = len(p_grid) * n_trials_per_grid_point

    # Seed capacity check against [0, 50_000) CALIBRATION range
    if seed_start + total_seeds_required > 50_000:
        raise SeedAllocationError(
            f"Requested {total_seeds_required} seeds starting from {seed_start} exceeds CALIBRATION range limit (50000)."
        )

    table_entries: List[CalibrationTableEntry] = []

    for g_idx, p_val in enumerate(p_grid):
        p_val_rounded = float(round(p_val, 4))
        
        # Handle p = 0 boundary degeneracy explicitly
        if p_val_rounded == 0.0:
            entry = CalibrationTableEntry(
                p=0.0,
                null_classification="DEGENERATE_BOUNDARY_NULL",
                empirical_critical_value=0.0,
                asymptotic_reference_applicability="NOT_REGULARLY_APPLICABLE",
                asymptotic_critical_value=None,
                n_trials=n_trials_per_grid_point,
                quantile_probability=1.0 - alpha,
            )
            table_entries.append(entry)
            continue

        # Regular interior points (p > 0)
        T_statistics = []
        for t_idx in range(n_trials_per_grid_point):
            offset = seed_start + g_idx * n_trials_per_grid_point + t_idx
            seed = SeedAllocator.get_seed("CALIBRATION", offset)

            config = SessionConfig(n_qubits=n_qubits, noise_parameter_p=p_val_rounded, seed=seed)
            transcript = run_session(config)
            evidence = extract_evidence(transcript)
            stage1_res = evaluate_stage1(evidence)
            T_statistics.append(stage1_res.statistic)

        T_arr = np.array(T_statistics, dtype=np.float64)
        emp_crit_val = float(np.quantile(T_arr, 1.0 - alpha, method="weibull"))
        asymp_crit_val = float(stats.chi2.ppf(1.0 - alpha, df=1))

        entry = CalibrationTableEntry(
            p=p_val_rounded,
            null_classification="REGULAR_INTERIOR_NULL",
            empirical_critical_value=emp_crit_val,
            asymptotic_reference_applicability="REGULAR_CHI2_DF1",
            asymptotic_critical_value=asymp_crit_val,
            n_trials=n_trials_per_grid_point,
            quantile_probability=1.0 - alpha,
        )
        table_entries.append(entry)

    canonical_payload = build_canonical_payload(
        schema_version=schema_version,
        architecture_version=architecture_version,
        stage1_model_version=stage1_model_version,
        n_qubits=n_qubits,
        alpha=alpha,
        n_trials_per_grid_point=n_trials_per_grid_point,
        p_grid=p_grid,
        seed_start=seed_start,
        seed_count=total_seeds_required,
        table_entries=table_entries,
    )

    content_hash = compute_canonical_hash(canonical_payload)
    artifact_dict = dict(canonical_payload)
    artifact_dict["content_hash"] = content_hash
    return artifact_dict


def run_monte_carlo_calibration(n_simulations: int = 1000) -> Dict[str, Any]:
    """Compatibility wrapper for api/main.py trigger_calibration route."""
    return generate_calibration_artifact(n_trials_per_grid_point=max(10, n_simulations // 7))

