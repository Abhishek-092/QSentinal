# QSENTINEL — Quantum-Inspired Cyber Threat Detection for Digital Signature Security

> **Problem Statement (PS-141):** Quantum-Inspired Cyber Threat Detection for Digital Signature Security

---

## 📌 Executive Overview

**QSENTINEL** is a runtime, non-AI/ML statistical monitoring layer operating alongside a teleportation-distributed Quantum Digital Signature (QS-L) digital-signature protocol. It observes classical measurement telemetry disclosed by the protocol to detect quantum channel manipulation, forgery attempts, replay attacks, impersonation, unauthorized verifications, and cross-session low-and-slow noise parameter drift.

### 🛡️ Critical System Identity & Non-Negotiable Invariants

- **Runtime Non-AI/ML Statistical Monitoring Layer:** QSENTINEL uses explicit likelihood functions, profile-likelihood goodness-of-fit testing, sequential hypothesis testing (SPRT), and generalized likelihood ratio CUSUM (GLR-CUSUM). It contains **zero AI/ML, neural networks, or learned models**.
- **Two Categorically Separate Decision Paths:**
  1. **AUTHORITATIVE PROTOCOL PATH (`qds/`):** Owns the deterministic acceptance/rejection decision of signature verification using statevector quantum teleportation simulation, Pauli eigenstate encoding, Bell measurements, Pauli corrections, projective measurements, and the asymmetric threshold rule ($s_a < s_v$).
  2. **ADVISORY MONITORING PATH (`qsentinel_monitor/`):** Processes immutable session transcripts post-verification to generate advisory threat annotations (`ACCEPT`, `FLAG_REJECT`, `FLAG_INVESTIGATE`, `MODEL_INVALID`).
- **Absolute Non-Interference Guarantee:** QSENTINEL's advisory output **never** overrides, mutates, blocks, delays, or feeds back into the protocol's authoritative decision.
- **Quantum Evidence Reframing:** Mismatch rate ($m$), correlation ($C=1-2p$), and entropy ($H$) are linked under the honest depolarizing model. They are evaluated via Stage 1 **joint mutual-consistency testing** against the single-parameter model to catch asymmetric/structural channel manipulation.

---

## 🏗️ System Architecture

```
                          Session Transcript (Frozen)
                                       │
                 ┌─────────────────────┴─────────────────────┐
                 │                                           │
     PROTOCOL EXECUTION EVIDENCE                    QUANTUM MEASUREMENT EVIDENCE
     (Deterministic - Authoritative)                 (Probabilistic - Advisory)
                 │                                           │
     FSM: freshness, authorization-scope,           Stage 1: Profile-Likelihood
     sequencing invariants                          Mutual-Consistency Check (m, C, H)
         ┌───────┴───────┐                                   │
         │               │                          ┌────────┴────────┐
       FAIL            PASS                     MODEL_VALID      MODEL_INVALID
         │               │                          │                 │
         ▼               │                          ▼                 ▼
   PROTOCOL REJECT       │                  Stage 2: Joint      FLAG (MODEL_INVALID)
  (Authoritative,        │                  Calibrated Decision  (Advisory)
   Terminal)             │                  (SPRT + Chi-Square)
                         │                          │
                         │                   ACCEPT / FLAG_REJECT / FLAG_INVESTIGATE
                         │                  (Advisory Only)
                         │                          │
                         │                          ├──────────────────────────┐
                         │                          ▼                          ▼
                         │                  Temporal GLR-CUSUM         Session Log Record
                         │                  (Unconditional Ingestion)
                         │                          │
                         └──────────────────────────┴──────────────────────────┐
                                                                               ▼
                                                            Signed, Hash-Chained Forensic Log
```

---

## 📁 Repository Structure

```text
qsentinel-system/                       # Repository Root
├── qds/                                # Authoritative Protocol Core (Pure, No dependencies on monitor)
│   ├── bell_pair.py                    # Bell-pair statevector preparation (|Φ+>)
│   ├── pauli.py                        # Pauli eigenstate encoding & corrections (I, X, Z, XZ)
│   ├── teleportation.py                # 3-qubit quantum teleportation engine
│   ├── measurement.py                  # BB84 random-basis projective measurements
│   ├── noise.py                        # Symmetric depolarizing channel model (parameter p)
│   ├── transcript.py                   # Frozen SessionTranscript & ProtocolDecision dataclasses
│   └── protocol.py                     # QS-L signature verification & threshold rule (s_a < s_v)
│
├── qsentinel_monitor/                  # Advisory Monitoring Overlay
│   ├── protocol_evidence/              # FSM, Freshness, & Authorization-scope checking
│   ├── quantum_evidence/               # Telemetry collector, Stage 1, Stage 2, GLR-CUSUM, Attribution
│   ├── orchestrator.py                 # Combines evidence paths into MonitoringDecision
│   └── forensic_log.py                 # Ed25519 signing & SHA-256 hash-chaining engine
│
├── attacks/                            # Attack Simulation Framework (7 Monte Carlo Conditions)
│   ├── base.py                         # Abstract AttackStrategy interface
│   ├── forgery.py                      # Clean & sub-threshold forgery attacks
│   ├── replay.py                       # Replay attack strategy
│   ├── impersonation.py                # Impersonation strategy (missing/invalid token)
│   ├── unauthorized_verification.py    # Unauthorized verification scope strategy
│   ├── channel_manipulation.py         # Intercept-resend, Pauli-structured, structural burst
│   └── low_and_slow.py                 # Low-and-slow noise parameter drift strategy
│
├── experiments/                        # Offline Calibration & Evaluation Harness
│   ├── seed_allocator.py               # Runtime SeedAllocator (CALIBRATION / VALIDATION / EVALUATION)
│   ├── calibration.py                  # Offline Stage 2 rejection region search (train/eval split)
│   ├── harness.py                      # 7-condition Monte Carlo harness (multiprocessing spawn context)
│   ├── ablation.py                     # Full-architecture-minus-one ablation testing
│   ├── verification_accuracy.py       # Legitimate acceptance sweep over noise p
│   ├── naive_baseline.py               # Naive multi-detector OR baseline comparator
│   └── alpha_spending_baseline.py      # Group-sequential alpha-spending comparator
│
├── db/                                 # Database & Persistence Layer
│   ├── models.py                       # SQLite SQLAlchemy models (CusumState sole persistence store)
│   └── migrations/                     # Alembic migrations (render_as_batch=True for SQLite)
│
├── forensic_store/                     # Authoritative Hash-Chained Forensic Record
│   └── chain_{date}.jsonl              # Append-only hash-chained JSONL files
│
├── artifacts/                          # Version-keyed & SHA-256 Content-Hashed Artifacts
│   └── calibration/{version}/          # artifact.json + region.npz
│
├── api/                                # FastAPI Backend Server
│   ├── main.py                         # Application startup & artifact verification
│   └── routes/                         # REST routes & SSE live stream endpoint
│
├── frontend/                           # React + Vite + Recharts Demo Dashboard
│   └── src/                            # 5 core interactive demo screens
│
├── tests/                              # 4-Tier Test Suite
│   ├── unit/                           # Isolated component & math formula tests
│   ├── integration/                    # Pipeline & multi-module integration tests
│   ├── statistical/                    # Monte Carlo & empirical distribution validation
│   └── regression/                     # Structural non-interference & schema version locking
│
└── .import-linter.cfg                  # CI-enforced contract: qds/ must NEVER import monitor or API
```

---

## 🛠️ Technology Stack

- **Core & Statistics:** Python 3.11+, NumPy, SciPy (`scipy.stats`, `scipy.optimize`)
- **Backend & Streaming:** FastAPI, Pydantic v2, Server-Sent Events (SSE)
- **Frontend & Visualization:** React, Vite, Recharts
- **Database & Migrations:** SQLite, Alembic (`render_as_batch=True`)
- **Forensics & Integrity:** `hashlib.sha256`, Ed25519 (`cryptography` package), append-only JSONL
- **Parallel Processing & Seeds:** `multiprocessing.Pool` (explicit `spawn` context), NumPy `PCG64` via runtime `SeedAllocator`
- **Architecture Enforcement:** `import-linter` (enforcing protocol purity in CI)
- **Testing:** `pytest` (4 tiers: unit, integration, statistical, regression)

---

## ⚡ Setup & Installation

### Prerequisites
- Python 3.11+
- Node.js 18+ (for frontend)

### Installation Steps

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Abhishek-092/QSentinal.git
   cd QSentinal
   ```

2. **Set up Python Virtual Environment:**
   ```bash
   python -m venv venv
   # Linux/macOS:
   source venv/bin/activate
   # Windows:
   .\venv\Scripts\activate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -e .
   ```

4. **Initialize Database & Run Migrations:**
   ```bash
   alembic upgrade head
   ```

5. **Run Architecture Boundary Check:**
   ```bash
   import-linter
   ```

6. **Run Test Suite:**
   ```bash
   pytest
   ```

---

## 🚀 Running the System

### Option A: Local Development Run (FastAPI + Vite)

1. **Start Backend API Server (Terminal 1):**
   ```bash
   python -m uvicorn api.main:app --host 127.0.0.1 --port 8000
   ```

2. **Start Frontend Dashboard (Terminal 2):**
   ```bash
   # From root directory:
   npm run dev

   # Or directly inside frontend folder:
   cd frontend && npm install && npm run dev
   ```
   Open [http://localhost:5173](http://localhost:5173) in your browser.

---

### Option B: Docker Container Run (Single Command)

Build and run both the API and persistent volumes (`./db`, `./forensic_store`) via Docker Compose:
```bash
docker compose up --build
```

---

### 3. Key CLI Operations & Experiments

* **Verify Forensic Hash Chain Integrity:**
  ```bash
  python -c "from qsentinel_monitor.forensic_log import verify_chain; print(verify_chain())"
  ```
  *(Or via API: `curl http://127.0.0.1:8000/api/forensics/verify`)*

* **Offline Stage 2 Calibration:**
  Generate the offline `CalibrationArtifact` on calibration seeds:
  ```bash
  python -m experiments.calibration --trials 50000 --output artifacts/calibration/v1/
  ```

* **Run Monte Carlo Attack Evaluation Harness:**
  Evaluate detection rates across attack conditions:
  ```bash
  python -m experiments.harness --trials 10000 --calibration-artifact artifacts/calibration/v1/artifact.json
  ```

---

## 🔬 Test Suite & Architectural Verification

Execute the complete 154-item test suite or specific test tiers:

```bash
# Run All Core Tests
pytest

# Run Unit Tests
pytest tests/unit

# Run Integration Tests
pytest tests/integration

# Run Statistical Validation Tests (Type I error & seed separation)
pytest tests/statistical

# Run Structural Non-Interference Regression Test
pytest tests/test_non_interference.py
```

---

## 📄 License & Attribution

Developed for **PS-141: Quantum-Inspired Cyber Threat Detection for Digital Signature Security**.
