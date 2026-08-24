import pytest
import numpy as np
from dataclasses import FrozenInstanceError
from qds.protocol import run_session, SessionConfig
from qds.bell_pair import prepare_bell_pair
from qds.pauli import encode_eigenstate
from qds.teleportation import teleport


def test_bell_pair_preparation():
    """Verify Bell state vector dimension and normalization."""
    bell = prepare_bell_pair()
    assert bell.shape == (4,)
    norm = float(np.linalg.norm(bell))
    assert pytest.approx(norm, 1e-6) == 1.0


def test_noiseless_quantum_teleportation_fidelity():
    """Verify 100% quantum teleportation fidelity under 0 noise across random states."""
    for bit in [0, 1]:
        for basis in [0, 1]:
            state = encode_eigenstate(bit, basis)
            (b0, b1), bob_state = teleport(state)
            fidelity = float(abs(np.vdot(state, bob_state)) ** 2)
            assert pytest.approx(fidelity, 1e-6) == 1.0


def test_noiseless_protocol_session_acceptance():
    """Verify deterministic signature acceptance under zero noise (p=0.0)."""
    config = SessionConfig(n_qubits=100, noise_parameter_p=0.0, seed=42)
    transcript = run_session(config)

    assert transcript.protocol_decision.accepted is True
    assert transcript.protocol_decision.mismatch_count == 0
    assert len(transcript.sifted_indices) > 0


def test_transcript_immutability():
    """Verify that SessionTranscript and ProtocolDecision are frozen dataclasses and raise on mutation."""
    config = SessionConfig(n_qubits=50, seed=123)
    transcript = run_session(config)

    with pytest.raises(FrozenInstanceError):
        transcript.protocol_decision = None

    with pytest.raises(FrozenInstanceError):
        transcript.sender_id = "adversary"
