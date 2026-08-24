"""
Offline Sequential Calibration Engine for QSENTINEL (Phase 6C).

Calibrates the maximum-over-horizon cumulative evidence statistic M_K = max(E_1, ..., E_K)
under honest-null execution using CALIBRATION seeds.
Produces versioned, SHA-256 content-hashed sequential calibration artifacts.
"""
from dataclasses import dataclass, asdict
from typing import Any
import json
import numpy as np

from qds.protocol import run_session, SessionConfig
from qsentinel_monitor.quantum_evidence import extract_evidence, evaluate_stage1
from qsentinel_monitor.calibration_loader import load_calibration_artifact, CalibrationArtifact
from qsentinel_monitor.calibrated_decision import evaluate_calibrated_stage1
from qsentinel_monitor.sequential_evidence import create_initial_sequential_state, update_sequential_evidence
from qsentinel_monitor.sequential_evidence_models import SessionProcessingOutcome
from qsentinel_monitor.sequential_calibration_loader import compute_sequential_canonical_hash
from experiments.seed_allocator import SeedAllocator, SeedAllocationError


def build_sequential_canonical_payload(
    schema_version: str,
    architecture_version: str,
    stage1_model_version: str,
    sequential_model_version: str,
    stage1_artifact: CalibrationArtifact,
    monitoring_horizon_sessions: int,
    alpha_seq: float,
    n_trials: int,
    seed_start: int,
    seed_count: int,
    empirical_sequential_threshold: float,
) -> dict[str, Any]:
    """
    Constructs deterministic canonical payload for sequential calibration artifact.
    Contains zero wall-clock timestamps or nondeterministic metadata.
    """
    return {
        "schema_version": schema_version,
        "architecture_version": architecture_version,
        "stage1_model_version": stage1_model_version,
        "sequential_model_version": sequential_model_version,
        "stage1_calibration_provenance": {
            "artifact_content_hash": stage1_artifact.content_hash,
            "schema_version": stage1_artifact.schema_version,
            "architecture_version": stage1_artifact.architecture_version,
            "stage1_model_version": stage1_artifact.stage1_model_version,
        },
        "sequential_configuration": {
            "monitoring_horizon_sessions": monitoring_horizon_sessions,
            "alpha_seq": alpha_seq,
            "n_trials": n_trials,
            "statistic_definition": "max_cumulative_evidence",
            "quantile_method": "weibull",
        },
        "seed_provenance": {
            "purpose": "CALIBRATION",
            "schedule_version": "v1.0",
            "seed_start": seed_start,
            "seed_count": seed_count,
            "mapping": "linear_trial_horizon_offset: seed_start + trial_idx * K + session_idx",
        },
        "empirical_sequential_threshold": float(empirical_sequential_threshold),
        "calibration_summary": {
            "finite_monte_carlo_estimate": True,
            "max_statistic_definition": "max(E_1, ..., E_K)",
        },
    }


def generate_sequential_calibration_artifact(
    stage1_artifact: CalibrationArtifact,
    monitoring_horizon_sessions: int = 20,
    alpha_seq: float = 0.01,
    n_trials: int = 2000,
    seed_start: int = 10000,  # Offset within CALIBRATION range [0, 50_000)
    honest_p_list: list[float | None] = None,
    tolerance: float = 0.05,
    schema_version: str = "1.0",
    architecture_version: str = "v5.0",
    stage1_model_version: str = "v1.0",
    sequential_model_version: str = "v1.0",
) -> dict[str, Any]:
    """
    Executes offline Monte Carlo simulation of M_K = max_{1..K} E_k under honest null execution.
    Enforces CALIBRATION seed capacity and produces content-hashed sequential calibration artifact.
    """
    total_sessions_required = n_trials * monitoring_horizon_sessions

    # Seed capacity check against [0, 50_000) CALIBRATION range limit
    if seed_start + total_sessions_required > 50_000:
        raise SeedAllocationError(
            f"Requested {total_sessions_required} calibration seeds starting from {seed_start} exceeds CALIBRATION range limit (50000)."
        )

    # Use interior p-grid points from stage1_artifact for honest noise simulation
    if honest_p_list is None:
        table_p = [float(entry["p"]) for entry in stage1_artifact.calibration_table if float(entry["p"]) > 0.0]
        honest_p_list = table_p if table_p else [0.10]

    max_E_list: list[float] = []

    for trial_idx in range(n_trials):
        seq_state = create_initial_sequential_state()
        trial_max_E = 0.0

        for session_idx in range(monitoring_horizon_sessions):
            offset = seed_start + trial_idx * monitoring_horizon_sessions + session_idx
            seed = SeedAllocator.get_seed("CALIBRATION", offset)

            # Cycle deterministically through valid interior honest p values
            p_sim = honest_p_list[session_idx % len(honest_p_list)]

            config = SessionConfig(n_qubits=200, noise_parameter_p=p_sim, seed=seed)
            transcript = run_session(config)
            evidence = extract_evidence(transcript)
            stage1_res = evaluate_stage1(evidence)
            calib_dec = evaluate_calibrated_stage1(stage1_res, stage1_artifact, tolerance=tolerance)

            res = update_sequential_evidence(seq_state, calib_dec)
            seq_state = res.next_state

            if seq_state.cumulative_evidence > trial_max_E:
                trial_max_E = seq_state.cumulative_evidence

        max_E_list.append(trial_max_E)

    max_E_arr = np.array(max_E_list, dtype=np.float64)
    empirical_tau_seq = float(np.quantile(max_E_arr, 1.0 - alpha_seq, method="weibull"))

    canonical_payload = build_sequential_canonical_payload(
        schema_version=schema_version,
        architecture_version=architecture_version,
        stage1_model_version=stage1_model_version,
        sequential_model_version=sequential_model_version,
        stage1_artifact=stage1_artifact,
        monitoring_horizon_sessions=monitoring_horizon_sessions,
        alpha_seq=alpha_seq,
        n_trials=n_trials,
        seed_start=seed_start,
        seed_count=total_sessions_required,
        empirical_sequential_threshold=empirical_tau_seq,
    )

    content_hash = compute_sequential_canonical_hash(canonical_payload)
    artifact_dict = dict(canonical_payload)
    artifact_dict["content_hash"] = content_hash
    return artifact_dict
