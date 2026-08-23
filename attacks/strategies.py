"""Modular attack simulation strategies for QSENTINEL evaluation.

Each strategy is a physically distinct channel or encoding mismatch, not a
cosmetic noise_p tweak.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from qds.protocol import SessionTranscript, run_session


@dataclass
class AttackResult:
    strategy: str
    transcript: SessionTranscript
    noise_override: float
    metadata: dict[str, Any]


class AttackStrategy(ABC):
    name: str
    noise_p: float = 0.02
    description: str = ""

    def execute(self, session_id: str) -> AttackResult:
        transcript = run_session(session_id, noise_p=self.noise_p, attack=self.name)
        return AttackResult(
            self.name,
            transcript,
            self.noise_p,
            {"type": self.name, "description": self.description},
        )


class CleanForgery(AttackStrategy):
    name = "clean_forgery"
    noise_p = 0.001
    description = "Forge |0⟩ instead of the authorized R_y(θ)|0⟩ message."


class SubThresholdForgery(AttackStrategy):
    name = "sub_threshold_forgery"
    noise_p = 0.02
    description = "Small Bloch-angle offset plus extra depolarizing drift."


class ReplayAttack(AttackStrategy):
    name = "replay"
    noise_p = 0.02
    description = "Reuse a product state with no fresh EPR pair."


class ImpersonationAttack(AttackStrategy):
    name = "impersonation"
    noise_p = 0.02
    description = "Substitute attacker state |1⟩ for the authorized |ψ(θ)⟩."


class UnauthorizedVerification(AttackStrategy):
    name = "unauthorized_verification"
    noise_p = 0.02
    description = "Skip Bob's X/Z Pauli correction after Bell measurement."


class ChannelManipulation(AttackStrategy):
    name = "channel_manipulation"
    noise_p = 0.02
    description = "Inject a strong depolarizing channel on the quantum link."


class LowAndSlowDrift(AttackStrategy):
    name = "low_and_slow_drift"
    noise_p = 0.02
    description = "Persistent extra depolarizing probability p≈0.025."


class InterceptResend(AttackStrategy):
    name = "intercept_resend"
    noise_p = 0.02
    description = "Measure Alice's EPR qubit in Z and collapse the Bell pair."


class BasisSpoof(AttackStrategy):
    name = "basis_spoof"
    noise_p = 0.02
    description = "Intercept Alice's EPR qubit in the X basis."


class EntanglementProbe(AttackStrategy):
    name = "entanglement_probe"
    noise_p = 0.02
    description = "Extra CNOT from Bob onto Alice's EPR half."


ATTACK_REGISTRY: dict[str, AttackStrategy] = {
    cls.name: cls()
    for cls in [
        CleanForgery,
        SubThresholdForgery,
        ReplayAttack,
        ImpersonationAttack,
        UnauthorizedVerification,
        ChannelManipulation,
        LowAndSlowDrift,
        InterceptResend,
        BasisSpoof,
        EntanglementProbe,
    ]
}

ATTACK_REGISTRY = ATTACK_REGISTRY


def run_attack(strategy_name: str, session_id: str) -> AttackResult:
    if strategy_name not in ATTACK_REGISTRY:
        raise ValueError(f"Unknown attack strategy: {strategy_name}")
    return ATTACK_REGISTRY[strategy_name].execute(session_id)
