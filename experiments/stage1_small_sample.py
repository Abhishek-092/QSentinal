"""
Offline analysis script comparing empirical finite-sample critical values against theoretical chi-square references.
"""
import numpy as np
import scipy.stats as stats
from typing import Any

from experiments.calibration import generate_calibration_artifact


def analyze_small_sample_behavior(
    p_grid: list[float] = [0.0, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30],
    n_qubits: int = 200,
    alpha: float = 0.01,
    n_trials: int = 200,
) -> dict[str, Any]:
    """
    Generates a calibration table and analyzes empirical vs asymptotic critical value differences across p_grid.
    """
    artifact = generate_calibration_artifact(
        p_grid=p_grid,
        n_qubits=n_qubits,
        alpha=alpha,
        n_trials_per_grid_point=n_trials,
    )

    comparison_results = []
    for entry in artifact["calibration_table"]:
        p_val = entry["p"]
        emp_val = entry["empirical_critical_value"]
        asymp_val = entry["asymptotic_critical_value"]
        classification = entry["null_classification"]

        if classification == "DEGENERATE_BOUNDARY_NULL":
            diff = 0.0
        else:
            diff = float(emp_val - asymp_val) if asymp_val is not None else 0.0

        comparison_results.append({
            "p": p_val,
            "classification": classification,
            "empirical_critical_value": emp_val,
            "asymptotic_critical_value": asymp_val,
            "empirical_minus_asymptotic_diff": diff,
        })

    return {
        "artifact_hash": artifact["content_hash"],
        "comparison_table": comparison_results,
    }


if __name__ == "__main__":
    res = analyze_small_sample_behavior()
    print("Small Sample Analysis Results:")
    print(res)
