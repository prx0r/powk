"""Model plugin interface.

A model receives a Snapshot and emits DERIVATIONs.
Models are versioned and identified by code hash.

Protocol:
    name        — human-readable model name
    version     — semver string
    model_hash  — SHA-256 of the model source file bytes
    requirements() — list of required observations
    compute(snapshot)  — run the model, return list[Derivation]
"""

import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List

from .snapshot import Snapshot
from .model import Derivation, make_deriv_id


def hash_file(path: str) -> str:
    """SHA-256 of a file's exact bytes (full 64 hex chars)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


class Model(ABC):
    """Base class for POWKernel models."""

    name: str = "unnamed"
    version: str = "0.0.0"
    _model_hash: str = None

    @classmethod
    def from_file(cls, path: str) -> "Model":
        """Load a model from a Python file and compute hash from exact bytes."""
        model = cls()
        model._model_hash = hash_file(path)
        return model

    @property
    def model_hash(self) -> str:
        """SHA-256 of this model's source code.

        If loaded via from_file(), uses the actual file bytes.
        Otherwise falls back to module name hash (less reliable).
        """
        if self._model_hash:
            return self._model_hash
        # Fallback: hash the source file if we can find it
        try:
            module = type(self).__module__
            if module and module != "__main__":
                import importlib
                mod = importlib.import_module(module)
                if hasattr(mod, "__file__") and mod.__file__:
                    return hash_file(mod.__file__)
        except Exception:
            pass
        # Last resort: hash class name (explicitly unreliable)
        return hashlib.sha256(type(self).__name__.encode()).hexdigest()

    @abstractmethod
    def requirements(self, snapshot: Snapshot = None) -> list:
        """List of required observations: [{"subject_kind": ..., "metric": ...}, ...]"""
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
