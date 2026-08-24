"""Append-only JSONL forensic log with SHA-256 hash chaining and Ed25519 signatures."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat

_DEFAULT_FORENSIC = Path(__file__).resolve().parent.parent / "forensic_store"
FORENSIC_DIR = Path(os.environ.get("QSENTINEL_FORENSIC_DIR", _DEFAULT_FORENSIC))
if os.environ.get("VERCEL"):
    FORENSIC_DIR = Path("/tmp/qsentinel_forensic")
LOG_FILE = FORENSIC_DIR / "forensic_chain.jsonl"
KEY_FILE = FORENSIC_DIR / "signing_key.pem"


def _ensure_key() -> Ed25519PrivateKey:
    FORENSIC_DIR.mkdir(parents=True, exist_ok=True)
    if KEY_FILE.exists():
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        return load_pem_private_key(KEY_FILE.read_bytes(), password=None)
    key = Ed25519PrivateKey.generate()
    KEY_FILE.write_bytes(
        key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    )
    return key


def _last_entry_hash() -> str:
    if not LOG_FILE.exists():
        return "0" * 64
    lines = LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
    if not lines or not lines[-1].strip():
        if len(lines) > 1:
            lines = [l for l in lines if l.strip()]
        if not lines:
            return "0" * 64
    try:
        last = json.loads(lines[-1])
        return last.get("entry_hash", "0" * 64)
    except json.JSONDecodeError:
        return _recover_torn_write(lines)


def _recover_torn_write(lines: list[str]) -> str:
    """Recover from torn trailing write by finding last valid entry."""
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
            if "entry_hash" in entry:
                return entry["entry_hash"]
        except json.JSONDecodeError:
            continue
    return "0" * 64


import msvcrt
import threading

_LOG_LOCK = threading.Lock()
LOCK_FILE = FORENSIC_DIR / ".forensic.lock"


class CrossProcessLock:
    def __enter__(self):
        FORENSIC_DIR.mkdir(parents=True, exist_ok=True)
        self.fp = open(LOCK_FILE, "a+")
        if os.name == "nt":
            msvcrt.locking(self.fp.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(self.fp.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if os.name == "nt":
                self.fp.seek(0)
                msvcrt.locking(self.fp.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self.fp.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        self.fp.close()


def append_log_entry(
    protocol_decision: Any,
    monitoring_decision: Any,
    telemetry: dict[str, Any],
) -> dict[str, Any]:
    """Append a tamper-proof hash-chained log entry with strict atomic cross-process serialization."""
    with _LOG_LOCK, CrossProcessLock():
        key = _ensure_key()
        prev_hash = _last_entry_hash()

        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "session_id": protocol_decision.session_id,
            "protocol_accepted": protocol_decision.accepted,
            "protocol_reason": protocol_decision.reason,
            "monitoring_verdict": monitoring_decision.verdict,
            "monitoring_details": monitoring_decision.details,
            "telemetry": telemetry,
            "prev_hash": prev_hash,
        }

        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        entry_hash = hashlib.sha256(canonical.encode()).hexdigest()
        signature = key.sign(entry_hash.encode()).hex()

        record = {**payload, "entry_hash": entry_hash, "signature": signature}

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
            f.flush()
            os.fsync(f.fileno())

        return record


def verify_chain() -> dict[str, Any]:
    """Verify full hash chain and Ed25519 signatures."""
    if not LOG_FILE.exists():
        return {"valid": True, "entries": 0, "details": "Empty log"}

    key = _ensure_key()
    public_key = key.public_key()
    lines = LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
    prev_hash = "0" * 64
    valid_count = 0

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            return {"valid": False, "entries": valid_count, "details": f"Torn write at line {i + 1}"}

        if entry.get("prev_hash") != prev_hash:
            return {
                "valid": False,
                "entries": valid_count,
                "details": f"Hash chain break at line {i + 1}",
            }

        entry_hash = entry.pop("entry_hash")
        signature_hex = entry.pop("signature")
        canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"))
        computed_hash = hashlib.sha256(canonical.encode()).hexdigest()

        if computed_hash != entry_hash:
            return {
                "valid": False,
                "entries": valid_count,
                "details": f"Hash mismatch at line {i + 1}",
            }

        try:
            public_key.verify(bytes.fromhex(signature_hex), entry_hash.encode())
        except Exception:
            return {
                "valid": False,
                "entries": valid_count,
                "details": f"Invalid signature at line {i + 1}",
            }

        prev_hash = entry_hash
        valid_count += 1

    return {"valid": True, "entries": valid_count, "details": "Chain integrity verified"}


def get_log_entries(limit: int = 100) -> list[dict]:
    if not LOG_FILE.exists():
        return []
    lines = LOG_FILE.read_text(encoding="utf-8").strip().split("\n")
    entries = []
    for line in lines[-limit:]:
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries
