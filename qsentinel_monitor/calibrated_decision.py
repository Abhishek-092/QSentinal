"""
Pure Runtime Calibrated Stage 1 Decision Engine for QSENTINEL (Phase 6A).

Evaluates Stage1Result against a pre-loaded, verified immutable CalibrationArtifact.
PERFORMS ZERO DISK IO, ZERO ARTIFACT LOADING, ZERO SEED ALLOCATION, ZERO MONTE CARLO SIMULATION,
AND ZERO RND/QDS PROTOCOL CALLS.
"""
import math
from typing import Optional, Dict, Any, List
from qsentinel_monitor.calibration_loader import CalibrationArtifact
from qsentinel_monitor.quantum_evidence.models import (
    Stage1Result,
    CalibratedStage1Decision,
    CalibrationLookupStatus,
    CalibratedDecisionStatus,
)


class CalibrationLookupError(ValueError):
    """Raised when calibration table data is malformed or ambiguous."""
    pass


def evaluate_calibrated_stage1(
    stage1_result: Stage1Result,
    artifact: CalibrationArtifact,
    tolerance: float = 1e-4,
) -> CalibratedStage1Decision:
    """
    Applies an already-loaded verified CalibrationArtifact to a Stage1Result.
    Follows strict artifact-driven lookup and p=0 boundary classification.
    Nearest-entry resolution is used when multiple entries fall within tolerance.
    """
    session_id = stage1_result.session_id
    raw_T = stage1_result.statistic
    p_hat = stage1_result.best_fit_p

    # Step 1 & 2: Validate Stage 1 availability and numerical sanity
    if (
        stage1_result.status != "PROCESSED"
        or not stage1_result.optimization_success
        or math.isnan(raw_T)
        or math.isinf(raw_T)
        or math.isnan(p_hat)
        or math.isinf(p_hat)
    ):
        return CalibratedStage1Decision(
            session_id=session_id,
            raw_statistic_t=raw_T,
            fitted_p_hat=p_hat,
            lookup_status=CalibrationLookupStatus.STAGE1_UNAVAILABLE,
            decision=CalibratedDecisionStatus.STAGE1_UNAVAILABLE,
            matched_calibration_p=None,
            empirical_critical_value=None,
            asymptotic_critical_value=None,
            margin_to_critical_value=None,
            artifact_content_hash=artifact.content_hash,
            artifact_schema_version=artifact.schema_version,
            architecture_version=artifact.architecture_version,
            stage1_model_version=artifact.stage1_model_version,
            diagnostic_reason="Stage 1 processing failed or produced non-finite statistics (NaN/Inf).",
        )

    # Step 3: Extract p-grid support from calibration table
    table = artifact.calibration_table
    p_values = [float(entry["p"]) for entry in table]

    if not p_values:
        raise CalibrationLookupError("Calibration table is empty.")

    p_min = min(p_values)
    p_max = max(p_values)

    # Step 4: Deterministic grid matching within tolerance
    matching_entries = [
        entry for entry in table if abs(float(entry["p"]) - p_hat) <= tolerance
    ]

    # Step 5: Process grid match (if found)
    if matching_entries:
        # If multiple grid points fall within tolerance, resolve deterministically to the closest grid point
        matched_entry = min(matching_entries, key=lambda e: abs(float(e["p"]) - p_hat))
        matched_p = float(matched_entry["p"])
        null_classification = matched_entry.get("null_classification", "")

        # Boundary Correction A & B: Respect artifact entry null_classification
        if null_classification == "DEGENERATE_BOUNDARY_NULL":
            return CalibratedStage1Decision(
                session_id=session_id,
                raw_statistic_t=raw_T,
                fitted_p_hat=p_hat,
                lookup_status=CalibrationLookupStatus.DEGENERATE_BOUNDARY,
                decision=CalibratedDecisionStatus.DEGENERATE_BOUNDARY,
                matched_calibration_p=matched_p,
                empirical_critical_value=0.0,
                asymptotic_critical_value=matched_entry.get("asymptotic_critical_value"),
                margin_to_critical_value=0.0,
                artifact_content_hash=artifact.content_hash,
                artifact_schema_version=artifact.schema_version,
                architecture_version=artifact.architecture_version,
                stage1_model_version=artifact.stage1_model_version,
                diagnostic_reason="Matched artifact DEGENERATE_BOUNDARY_NULL entry at p=0.0.",
            )

        # Regular interior grid point match
        emp_crit_val = float(matched_entry["empirical_critical_value"])
        asymp_crit_val = matched_entry.get("asymptotic_critical_value")
        if asymp_crit_val is not None:
            asymp_crit_val = float(asymp_crit_val)

        is_consistent = raw_T <= emp_crit_val
        decision_status = (
            CalibratedDecisionStatus.MODEL_CONSISTENT
            if is_consistent
            else CalibratedDecisionStatus.MODEL_INCONSISTENT
        )

        margin = float(emp_crit_val - raw_T)

        return CalibratedStage1Decision(
            session_id=session_id,
            raw_statistic_t=raw_T,
            fitted_p_hat=p_hat,
            lookup_status=CalibrationLookupStatus.EXACT_MATCH,
            decision=decision_status,
            matched_calibration_p=matched_p,
            empirical_critical_value=emp_crit_val,
            asymptotic_critical_value=asymp_crit_val,
            margin_to_critical_value=margin,
            artifact_content_hash=artifact.content_hash,
            artifact_schema_version=artifact.schema_version,
            architecture_version=artifact.architecture_version,
            stage1_model_version=artifact.stage1_model_version,
            diagnostic_reason=f"Matched calibration grid point p={matched_p}. Decision driven by empirical critical value {emp_crit_val}.",
        )

    # Step 6: No match within tolerance found
    if p_hat < p_min - tolerance or p_hat > p_max + tolerance:
        return CalibratedStage1Decision(
            session_id=session_id,
            raw_statistic_t=raw_T,
            fitted_p_hat=p_hat,
            lookup_status=CalibrationLookupStatus.CALIBRATION_OUT_OF_SUPPORT,
            decision=CalibratedDecisionStatus.CALIBRATION_OUT_OF_SUPPORT,
            matched_calibration_p=None,
            empirical_critical_value=None,
            asymptotic_critical_value=None,
            margin_to_critical_value=None,
            artifact_content_hash=artifact.content_hash,
            artifact_schema_version=artifact.schema_version,
            architecture_version=artifact.architecture_version,
            stage1_model_version=artifact.stage1_model_version,
            diagnostic_reason=f"Fitted p_hat {p_hat} is outside calibrated support [{p_min}, {p_max}]. Extrapolation strictly prohibited.",
        )

    # p_hat is within [p_min, p_max] but between grid points
    return CalibratedStage1Decision(
        session_id=session_id,
        raw_statistic_t=raw_T,
        fitted_p_hat=p_hat,
        lookup_status=CalibrationLookupStatus.CALIBRATION_UNAVAILABLE,
        decision=CalibratedDecisionStatus.CALIBRATION_UNAVAILABLE,
        matched_calibration_p=None,
        empirical_critical_value=None,
        asymptotic_critical_value=None,
        margin_to_critical_value=None,
        artifact_content_hash=artifact.content_hash,
        artifact_schema_version=artifact.schema_version,
        architecture_version=artifact.architecture_version,
        stage1_model_version=artifact.stage1_model_version,
        diagnostic_reason=f"Fitted p_hat {p_hat} lies between calibrated grid points. Interpolation strictly prohibited.",
    )
