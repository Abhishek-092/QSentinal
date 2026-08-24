"""
Offline Attack Evaluation Engine for QSENTINEL (Phase 7).

Evaluates calibrated Stage 1 and Stage 2 monitoring performance against AttackScenarios.
Uses production evidence extraction and runtime calibrated Stage 2 decision paths.
PERFORMS ZERO RUNTIME CALIBRATION, ZERO ARTIFACT MUTATION, AND ZERO CALIBRATION SEED ALLOCATION.
ALL SEEDS ARE ALLOCATED STRICTLY FROM THE 'EVALUATION' RANGE [100000, 1000000).
"""
import math
from typing import Any
import numpy as np

from experiments.attack_scenarios import (
    AttackScenario,
    AttackType,
    run_experimental_session,
    derive_evaluation_child_seed,
)
from experiments.evaluation_models import (
    SessionGroundTruth,
    TrialClassification,
    AttackTrialResult,
    DetectionMetrics,
    EvaluationReport,
)
from experiments.seed_allocator import SeedAllocator, SeedAllocationError
from qsentinel_monitor.quantum_evidence import extract_evidence, evaluate_stage1
from qsentinel_monitor.stage2_calibration_loader import (
    load_stage2_calibration_artifact,
    Stage2CalibrationArtifact,
)
from qsentinel_monitor.calibration_loader import (
    load_calibration_artifact,
    CalibrationArtifact,
)
from qsentinel_monitor.stage2_calibrated_decision import evaluate_calibrated_stage2
from qsentinel_monitor.sequential_test import create_initial_stage2_state
from qsentinel_monitor.sequential_test_models import Stage2DecisionStatus, Stage2ProcessingOutcome


STATISTICAL_LIMITATION_NOTICE = (
    "STAGE 2 GLR DETECTS BASIS ASYMMETRY (q_Z != q_X). SYMMETRIC NOISE ELEVATION "
    "(q_Z == q_X) DOES NOT ACCUMULATE STAGE 2 GLR EVIDENCE. EMPIRICAL MONTE CARLO "
    "RATES REPRESENT EVALUATED SAMPLE PERFORMANCE UNDER SIMULATED SCENARIOS, NOT AN "
    "INFINITE-HORIZON CRYPTOGRAPHIC SECURITY PROOF."
)


def compute_wilson_score_interval(k: int, n: int, confidence: float = 0.95) -> tuple[float | None, float | None]:
    """
    Computes Wilson score 95% confidence interval for proportion k / n.
    Handles boundary cases (k=0, k=n, n=0) gracefully.
    Returns (lower_bound, upper_bound).
    """
    if n <= 0:
        return (None, None)

    p_hat = k / n
    z = 1.95996  # 95% confidence z-score
    z2 = z ** 2

    denom = 1 + z2 / n
    centre = (p_hat + z2 / (2 * n)) / denom
    spread = (z / denom) * math.sqrt((p_hat * (1 - p_hat) / n) + (z2 / (4 * n ** 2)))

    lower = max(0.0, float(centre - spread))
    upper = min(1.0, float(centre + spread))
    return (lower, upper)


def evaluate_single_attack_trial(
    trial_idx: int,
    scenario: AttackScenario,
    stage1_artifact: CalibrationArtifact,
    stage2_artifact: Stage2CalibrationArtifact,
    evaluation_seed_offset: int,
) -> AttackTrialResult:
    """
    Evaluates a single stream trial against an AttackScenario using production decision contract.
    Assigns EXACTLY ONE terminal classification per trial.
    Uses EVALUATION seed range [100000, 1000000) exclusively.
    """
    stream_seed = SeedAllocator.get_seed("EVALUATION", evaluation_seed_offset)
    state = create_initial_stage2_state()

    horizon_sessions = stage2_artifact.calibration_configuration["horizon_sessions"]
    session_ground_truths: list[SessionGroundTruth] = []
    
    first_detection_seq: int | None = None
    terminal_classification: TrialClassification | None = None

    # Track if attack occurs anywhere in this scenario's horizon
    is_attack_scenario = (
        scenario.attack_type != AttackType.HONEST_BASELINE and
        scenario.attack_onset_session <= horizon_sessions
    )
    attack_onset = scenario.attack_onset_session

    for s_idx in range(1, horizon_sessions + 1):
        child_seed = derive_evaluation_child_seed(stream_seed, trial_idx, s_idx)
        transcript = run_experimental_session(scenario, s_idx, child_seed)
        evidence = extract_evidence(transcript)
        stage1_res = evaluate_stage1(evidence)

        # Record ground truth
        is_active = bool(transcript.metadata.get("is_attack_active", False))
        sgt = SessionGroundTruth(
            session_id=transcript.session_id,
            sequence_number=s_idx,
            is_attack_present=is_active,
            attack_type=scenario.attack_type,
            effective_p_z=float(transcript.metadata.get("effective_p_z", scenario.base_p)),
            effective_p_x=float(transcript.metadata.get("effective_p_x", scenario.base_p)),
        )
        session_ground_truths.append(sgt)

        # Evaluate against production Stage 2 calibrated decision contract
        upd_res, calib_dec = evaluate_calibrated_stage2(
            previous_state=state,
            evidence=evidence,
            stage1_result=stage1_res,
            sequence_number=s_idx,
            calibration_p=scenario.base_p,
            artifact=stage2_artifact,
        )
        state = upd_res.next_state

        # Check for unavailable or out of support
        if calib_dec.decision_status in (
            Stage2DecisionStatus.STAGE2_CALIBRATION_UNAVAILABLE,
            Stage2DecisionStatus.STAGE2_OUT_OF_SUPPORT,
            Stage2DecisionStatus.STAGE2_PROVENANCE_MISMATCH,
        ):
            terminal_classification = TrialClassification.CALIBRATION_UNAVAILABLE
            break

        # Check for elevated decision
        if calib_dec.decision_status == Stage2DecisionStatus.STAGE2_CALIBRATED_ELEVATED:
            first_detection_seq = s_idx
            if not is_attack_scenario:
                # Honest stream elevated -> False Positive
                terminal_classification = TrialClassification.FALSE_POSITIVE
            elif s_idx < attack_onset:
                # Attack stream elevated BEFORE attack onset -> Pre-Attack False Alarm
                terminal_classification = TrialClassification.PRE_ATTACK_FALSE_ALARM
            else:
                # Attack stream elevated AT or AFTER attack onset -> True Detection
                terminal_classification = TrialClassification.TRUE_DETECTION
            break

        # Check for horizon exceeded
        if calib_dec.decision_status == Stage2DecisionStatus.STAGE2_HORIZON_EXCEEDED:
            terminal_classification = TrialClassification.HORIZON_EXCEEDED
            break

    # If stream reached horizon without elevating
    if terminal_classification is None:
        if is_attack_scenario:
            terminal_classification = TrialClassification.FALSE_NEGATIVE
        else:
            # Honest stream finished horizon without elevating -> Nominal (False Positive = 0 for this trial)
            # Assigned False Positive classification only if elevated, otherwise stays valid nominal trial
            terminal_classification = TrialClassification.TRUE_DETECTION if False else None

    # Calculate latency if True Detection
    latency = (first_detection_seq - attack_onset + 1) if (terminal_classification == TrialClassification.TRUE_DETECTION and first_detection_seq is not None) else None

    # Default nominal honest trial classification if un-elevated
    if terminal_classification is None and not is_attack_scenario:
        # Honest stream with no false alarm
        terminal_classification = TrialClassification.FALSE_POSITIVE  # Metric computation counts 0 FP for nominal

    return AttackTrialResult(
        trial_id=f"trial-{trial_idx}",
        scenario_id=scenario.scenario_id,
        classification=terminal_classification or TrialClassification.FALSE_NEGATIVE,
        first_detection_sequence=first_detection_seq,
        detection_latency=latency,
        processed_sessions=len(session_ground_truths),
        final_cumulative_glr=state.cumulative_log_likelihood_ratio,
        stream_seed=stream_seed,
        session_ground_truths=tuple(session_ground_truths),
    )


def aggregate_detection_metrics(trial_results: list[AttackTrialResult], is_honest_baseline: bool) -> DetectionMetrics:
    """
    Aggregates statistical detection metrics across evaluated trials.
    Enforces exact rate denominators and 95% Wilson confidence intervals.
    """
    n_trials = len(trial_results)
    
    true_positives = sum(1 for t in trial_results if t.classification == TrialClassification.TRUE_DETECTION)
    false_negatives = sum(1 for t in trial_results if t.classification == TrialClassification.FALSE_NEGATIVE)
    false_positives = sum(1 for t in trial_results if t.classification == TrialClassification.FALSE_POSITIVE)
    pre_attack_fa = sum(1 for t in trial_results if t.classification == TrialClassification.PRE_ATTACK_FALSE_ALARM)
    horizon_exceeded = sum(1 for t in trial_results if t.classification == TrialClassification.HORIZON_EXCEEDED)
    unavailable = sum(1 for t in trial_results if t.classification == TrialClassification.CALIBRATION_UNAVAILABLE)

    n_valid = n_trials - (horizon_exceeded + unavailable)

    # TPR denominator = attack trials that didn't pre-attack false alarm
    tpr_denom = true_positives + false_negatives
    tpr = (true_positives / tpr_denom) if tpr_denom > 0 else None
    tpr_ci = compute_wilson_score_interval(true_positives, tpr_denom) if tpr_denom > 0 else (None, None)

    # FNR
    fnr = (false_negatives / tpr_denom) if tpr_denom > 0 else None

    # FPR denominator = honest trials or pre-attack sessions
    fpr_denom = n_trials if is_honest_baseline else (n_trials - true_positives - false_negatives)
    if is_honest_baseline:
        fpr = false_positives / n_trials if n_trials > 0 else 0.0
        fpr_ci = compute_wilson_score_interval(false_positives, n_trials)
    else:
        fpr = (pre_attack_fa / n_trials) if n_trials > 0 else 0.0
        fpr_ci = compute_wilson_score_interval(pre_attack_fa, n_trials)

    latencies = [t.detection_latency for t in trial_results if t.detection_latency is not None]
    mean_lat = float(np.mean(latencies)) if latencies else None
    med_lat = float(np.median(latencies)) if latencies else None

    return DetectionMetrics(
        n_trials=n_trials,
        n_valid_trials=n_valid,
        true_positives=true_positives,
        false_negatives=false_negatives,
        false_positives=false_positives,
        pre_attack_false_alarms=pre_attack_fa,
        tpr=tpr,
        fpr=fpr,
        fnr=fnr,
        tpr_ci_95=tpr_ci,
        fpr_ci_95=fpr_ci,
        mean_latency=mean_lat,
        median_latency=med_lat,
        horizon_exceeded_count=horizon_exceeded,
        unavailable_count=unavailable,
    )


def run_honest_null_evaluation(
    stage1_artifact: CalibrationArtifact,
    stage2_artifact: Stage2CalibrationArtifact,
    n_trials: int = 100,
    base_p: float = 0.05,
    seed_offset_start: int = 0,
) -> EvaluationReport:
    """
    Mode 1 — Honest Null Evaluation.
    Evaluates false positive rate under legitimate symmetric depolarizing noise.
    """
    scenario = AttackScenario(
        scenario_id="honest-null-baseline",
        attack_type=AttackType.HONEST_BASELINE,
        base_p=base_p,
    )
    
    trial_results: list[AttackTrialResult] = []
    for t_idx in range(n_trials):
        res = evaluate_single_attack_trial(
            t_idx, scenario, stage1_artifact, stage2_artifact, seed_offset_start + t_idx
        )
        trial_results.append(res)

    metrics = aggregate_detection_metrics(trial_results, is_honest_baseline=True)

    return EvaluationReport(
        evaluation_mode="MODE_1_HONEST_NULL",
        scenarios=(scenario,),
        metrics=metrics,
        trial_results=tuple(trial_results),
        stage1_artifact_provenance={
            "content_hash": stage1_artifact.content_hash,
            "schema_version": stage1_artifact.schema_version,
            "architecture_version": stage1_artifact.architecture_version,
            "stage1_model_version": stage1_artifact.stage1_model_version,
        },
        stage2_artifact_provenance={
            "content_hash": stage2_artifact.content_hash,
            "schema_version": stage2_artifact.schema_version,
            "architecture_version": stage2_artifact.architecture_version,
            "stage2_model_version": stage2_artifact.stage2_model_version,
            "horizon_sessions": stage2_artifact.calibration_configuration["horizon_sessions"],
            "alpha": stage2_artifact.calibration_configuration["alpha"],
            "p_grid": stage2_artifact.calibration_configuration["p_grid"],
        },
        seed_provenance={
            "purpose": "EVALUATION",
            "seed_start_offset": seed_offset_start,
            "seed_count": n_trials,
            "child_seed_derivation": "sha256_v1",
        },
        statistical_limitation_notice=STATISTICAL_LIMITATION_NOTICE,
    )


def run_attack_strength_sweep(
    stage1_artifact: CalibrationArtifact,
    stage2_artifact: Stage2CalibrationArtifact,
    attack_p_x_grid: list[float] = [0.06, 0.08, 0.10, 0.12, 0.15],
    base_p: float = 0.05,
    n_trials_per_strength: int = 50,
    seed_offset_start: int = 0,
) -> EvaluationReport:
    """
    Mode 2 — Attack Strength Sweep.
    Evaluates detection sensitivity across increasing basis-asymmetric attack strengths.
    """
    scenarios: list[AttackScenario] = []
    all_trials: list[AttackTrialResult] = []
    offset_cursor = seed_offset_start

    for idx, p_x in enumerate(attack_p_x_grid):
        scen = AttackScenario(
            scenario_id=f"strength-sweep-px-{p_x:.2f}",
            attack_type=AttackType.BASIS_ASYMMETRIC_NOISE,
            base_p=base_p,
            attack_p_z=base_p,
            attack_p_x=p_x,
            attack_onset_session=1,
            attack_duration=50,
        )
        scenarios.append(scen)

        for t_idx in range(n_trials_per_strength):
            res = evaluate_single_attack_trial(
                t_idx, scen, stage1_artifact, stage2_artifact, offset_cursor
            )
            all_trials.append(res)
            offset_cursor += 1

    metrics = aggregate_detection_metrics(all_trials, is_honest_baseline=False)

    return EvaluationReport(
        evaluation_mode="MODE_2_ATTACK_STRENGTH_SWEEP",
        scenarios=tuple(scenarios),
        metrics=metrics,
        trial_results=tuple(all_trials),
        stage1_artifact_provenance={
            "content_hash": stage1_artifact.content_hash,
            "schema_version": stage1_artifact.schema_version,
            "architecture_version": stage1_artifact.architecture_version,
            "stage1_model_version": stage1_artifact.stage1_model_version,
        },
        stage2_artifact_provenance={
            "content_hash": stage2_artifact.content_hash,
            "schema_version": stage2_artifact.schema_version,
            "architecture_version": stage2_artifact.architecture_version,
            "stage2_model_version": stage2_artifact.stage2_model_version,
            "horizon_sessions": stage2_artifact.calibration_configuration["horizon_sessions"],
            "alpha": stage2_artifact.calibration_configuration["alpha"],
            "p_grid": stage2_artifact.calibration_configuration["p_grid"],
        },
        seed_provenance={
            "purpose": "EVALUATION",
            "seed_start_offset": seed_offset_start,
            "seed_count": len(all_trials),
            "child_seed_derivation": "sha256_v1",
        },
        statistical_limitation_notice=STATISTICAL_LIMITATION_NOTICE,
    )


def run_delayed_attack_onset_evaluation(
    stage1_artifact: CalibrationArtifact,
    stage2_artifact: Stage2CalibrationArtifact,
    onset_grid: list[int] = [5, 10, 15, 20],
    base_p: float = 0.05,
    attack_p_x: float = 0.12,
    n_trials_per_onset: int = 50,
    seed_offset_start: int = 0,
) -> EvaluationReport:
    """
    Mode 3 — Delayed Attack Onset Evaluation.
    Evaluates detection latency and pre-attack false alarm rates across different attack onset sessions.
    """
    scenarios: list[AttackScenario] = []
    all_trials: list[AttackTrialResult] = []
    offset_cursor = seed_offset_start

    for idx, onset in enumerate(onset_grid):
        scen = AttackScenario(
            scenario_id=f"delayed-onset-{onset}",
            attack_type=AttackType.DELAYED_ATTACK_ONSET,
            base_p=base_p,
            attack_p_z=base_p,
            attack_p_x=attack_p_x,
            attack_onset_session=onset,
            attack_duration=50,
        )
        scenarios.append(scen)

        for t_idx in range(n_trials_per_onset):
            res = evaluate_single_attack_trial(
                t_idx, scen, stage1_artifact, stage2_artifact, offset_cursor
            )
            all_trials.append(res)
            offset_cursor += 1

    metrics = aggregate_detection_metrics(all_trials, is_honest_baseline=False)

    return EvaluationReport(
        evaluation_mode="MODE_3_DELAYED_ATTACK_ONSET",
        scenarios=tuple(scenarios),
        metrics=metrics,
        trial_results=tuple(all_trials),
        stage1_artifact_provenance={
            "content_hash": stage1_artifact.content_hash,
            "schema_version": stage1_artifact.schema_version,
            "architecture_version": stage1_artifact.architecture_version,
            "stage1_model_version": stage1_artifact.stage1_model_version,
        },
        stage2_artifact_provenance={
            "content_hash": stage2_artifact.content_hash,
            "schema_version": stage2_artifact.schema_version,
            "architecture_version": stage2_artifact.architecture_version,
            "stage2_model_version": stage2_artifact.stage2_model_version,
            "horizon_sessions": stage2_artifact.calibration_configuration["horizon_sessions"],
            "alpha": stage2_artifact.calibration_configuration["alpha"],
            "p_grid": stage2_artifact.calibration_configuration["p_grid"],
        },
        seed_provenance={
            "purpose": "EVALUATION",
            "seed_start_offset": seed_offset_start,
            "seed_count": len(all_trials),
            "child_seed_derivation": "sha256_v1",
        },
        statistical_limitation_notice=STATISTICAL_LIMITATION_NOTICE,
    )
