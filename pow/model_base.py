"""Model plugin interface.

A model receives a Snapshot and emits DERIVATIONs.
Models are versioned and identified by code hash.

Protocol:
    name        — human-readable model name
    version     — semver string
    model_hash  — SHA-256 of the model code (for derivation reproducibility)
    required_inputs() — list of (metric, kind) pairs the model needs
    compute(snapshot)  — run the model, return list[Derivation]
"""

import hashlib
from abc import ABC, abstractmethod
from typing import List

from .snapshot import Snapshot
from .model import Derivation, make_deriv_id


class Model(ABC):
    """Base class for POWKernel models."""

    name: str = "unnamed"
    version: str = "0.0.0"

    @property
    def model_hash(self) -> str:
        """SHA-256 of this model's source code."""
        source = hashlib.sha256()
        try:
            source.update(type(self).__module__.encode())
        except Exception:
            source.update(b"unknown")
        return source.hexdigest()[:16]

    @abstractmethod
    def required_inputs(self) -> list:
        """List of (metric, kind) pairs this model needs from the snapshot."""
        pass

    @abstractmethod
    def compute(self, snapshot: Snapshot) -> List[Derivation]:
        """Run the model against a snapshot. Return derivations."""
        pass

    def _make_derivation(self, kind: str, subject: str, value: float,
                         unit: str, effective_at: str, inputs: list,
                         unknowns: list = None) -> Derivation:
        """Helper to create a Derivation with proper content-addressed ID."""
        did = make_deriv_id(
            kind=kind, subject=subject,
            model=f"{self.name}/{self.version}",
            model_hash=self.model_hash,
            effective_at=effective_at,
            inputs=inputs,
        )
        return Derivation(
            id=did,
            kind=kind,
            subject=subject,
            value=value,
            unit=unit,
            effective_at=effective_at,
            model=f"{self.name}/{self.version}",
            model_hash=self.model_hash,
            inputs=inputs,
            unknowns=unknowns or [],
        )
