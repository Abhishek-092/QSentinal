"""QSENTINEL Core API — session execution, experiments, forensics, CUSUM, SSE."""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from attacks.strategies import ATTACK_REGISTRY, run_attack
from db.models import init_db
from experiments.calibration import run_monte_carlo_calibration
from qds.protocol import iterate_session, run_session
from qsentinel_monitor.forensic_log import append_log_entry, get_log_entries, verify_chain
from qsentinel_monitor.glr_cusum import GLRCusumMonitor
from qsentinel_monitor.orchestrator import analyze, get_calibration


def _bootstrap() -> None:
    init_db()
    get_calibration()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _bootstrap()
    yield


router = APIRouter()
app = FastAPI(title="QSENTINEL Core API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_cusum = GLRCusumMonitor()

if os.environ.get("VERCEL"):
    _bootstrap()


class SessionRequest(BaseModel):
    session_id: str | None = None
    noise_p: float = 0.02
    theta: float = 0.7853981633974483


class AttackRequest(BaseModel):
    strategy: str
    session_id: str | None = None


def _json_default(obj: Any):
    if hasattr(obj, "item") and callable(obj.item):
        return obj.item()
    if hasattr(obj, "tolist") and callable(obj.tolist):
        return obj.tolist()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def _dumps(payload: dict) -> str:
    return json.dumps(payload, default=_json_default)


def _serialize_session(
    session_id: str,
    transcript: Any,
    monitoring: Any,
) -> dict[str, Any]:
    mismatch_rate = transcript.measurement_telemetry.get("mismatch_rate", 0.0)
    cusum_update = _cusum.update(session_id, mismatch_rate)

    return {
        "session_id": session_id,
        "protocol_decision": {
            "accepted": transcript.protocol_decision.accepted,
            "reason": transcript.protocol_decision.reason,
        },
        "monitoring_decision": {
            "verdict": monitoring.verdict,
            "advisory": monitoring.advisory,
            "details": monitoring.details,
            "stage1_passed": monitoring.stage1_passed,
            "stage2_passed": monitoring.stage2_passed,
            "fsm_passed": monitoring.fsm_passed,
            "cusum_value": cusum_update.cusum_value,
            "drift_detected": cusum_update.drift_detected,
        },
        "telemetry": transcript.measurement_telemetry,
    }



@router.get("/health")
def health():
    cal = get_calibration()
    return {"status": "ok", "calibration_hash": cal.content_hash[:16]}


@router.post("/sessions/run")
def execute_session(body: SessionRequest | None = None):
    req = body or SessionRequest()
    session_id = req.session_id or f"sess-{uuid.uuid4().hex[:8]}"
    transcript = run_session(session_id, noise_p=req.noise_p, theta=req.theta)
    monitoring_decision = analyze(transcript, transcript.protocol_decision)
    append_log_entry(transcript.protocol_decision, monitoring_decision, transcript.measurement_telemetry)
    return _serialize_session(session_id, transcript, monitoring_decision)


@router.get("/sessions/{session_id}/stream")
async def session_stream(
    session_id: str,
    noise_p: float = Query(0.02),
    theta: float = Query(0.7853981633974483),
):
    async def event_generator():
        transcript = None
        for event in iterate_session(session_id, noise_p=noise_p, theta=theta):
            await asyncio.sleep(0.35)
            if event.get("transcript") is not None:
                transcript = event["transcript"]
            yield {
                "event": "progress",
                "data": _dumps({
                    "step": event.get("phase") or event.get("step"),
                    "progress": event.get("progress", 0),
                    "snapshot": event.get("snapshot"),
                }),
            }

        if transcript is None:
            transcript = run_session(session_id, noise_p=noise_p, theta=theta)
        decision = analyze(transcript, transcript.protocol_decision)
        append_log_entry(transcript.protocol_decision, decision, transcript.measurement_telemetry)
        mismatch_rate = transcript.measurement_telemetry.get("mismatch_rate", 0.0)
        cusum_update = _cusum.update(session_id, mismatch_rate)
        yield {
            "event": "complete",
            "data": _dumps({
                "session_id": session_id,
                "accepted": transcript.protocol_decision.accepted,
                "reason": transcript.protocol_decision.reason,
                "verdict": decision.verdict,
                "details": decision.details,
                "telemetry": transcript.measurement_telemetry,
                "snapshot": transcript.measurement_telemetry,
                "monitoring": {
                    "stage1_passed": decision.stage1_passed,
                    "stage2_passed": decision.stage2_passed,
                    "cusum_value": cusum_update.cusum_value,
                    "drift_detected": cusum_update.drift_detected,
                },
            }),
        }

    return EventSourceResponse(event_generator())


@router.post("/attacks/run")
def execute_attack(body: AttackRequest):
    if body.strategy not in ATTACK_REGISTRY:
        raise HTTPException(400, f"Unknown strategy. Available: {list(ATTACK_REGISTRY.keys())}")
    session_id = body.session_id or f"attack-{uuid.uuid4().hex[:8]}"
    attack_result = run_attack(body.strategy, session_id)
    transcript = attack_result.transcript
    monitoring_decision = analyze(transcript, transcript.protocol_decision)
    append_log_entry(transcript.protocol_decision, monitoring_decision, transcript.measurement_telemetry)
    result = _serialize_session(session_id, transcript, monitoring_decision)
    result["attack"] = {"strategy": attack_result.strategy, "metadata": attack_result.metadata}
    return result


@router.get("/attacks/strategies")
def list_strategies():
    return {"strategies": list(ATTACK_REGISTRY.keys())}


@router.post("/experiments/calibrate")
def trigger_calibration(n_simulations: int = Query(1000, ge=100, le=50000)):
    artifact = run_monte_carlo_calibration(n_simulations)
    import qsentinel_monitor.orchestrator as orch
    orch._calibration = None
    get_calibration()
    return {"status": "calibrated", "artifact": artifact}


@router.get("/forensics/log")
def forensic_log(limit: int = Query(100, ge=1, le=1000)):
    return {"entries": get_log_entries(limit)}


@router.get("/forensics/verify")
def forensic_verify():
    return verify_chain()


@router.get("/cusum/history")
def cusum_history(limit: int = Query(50, ge=1, le=500)):
    return {"history": _cusum.get_history(limit)}


@router.get("/calibration")
def calibration_info():
    cal = get_calibration()
    return {
        "content_hash": cal.content_hash,
        "rejection_threshold": cal.rejection_threshold,
        "s_sprt_threshold": cal.s_sprt_threshold,
        "s_gate_threshold": cal.s_gate_threshold,
        "metadata": cal.metadata,
    }


@app.get("/")
def root():
    return {
        "service": "QSENTINEL Core API",
        "health": "/api/health",
        "docs": "/docs",
    }


# Mounted twice so routes work whether Vercel keeps /api or strips it.
app.include_router(router, prefix="/api")
app.include_router(router, include_in_schema=False)