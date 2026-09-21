"""Pressure v1 — demand/supply ratio model.

A simple constraint pressure model that computes the ratio of
demand to supply for each edge in the dependency graph.

This is a MODEL, not kernel truth. It lives in models/ for a reason.
"""

import hashlib
from typing import List

from pow.model_base import Model
from pow.snapshot import Snapshot
from pow.model import Derivation


class PressureV1(Model):
    name = "pressure"
    version = "1.0.0"

    def required_inputs(self) -> list:
        return [("capacity", "any")]

    def compute(self, snapshot: Snapshot) -> List[Derivation]:
        derivations = []
        for edge in snapshot.edges.values():
            source_obs = snapshot.observation(edge.source, "capacity")
            target_obs = snapshot.observation(edge.target, "capacity")

            demand = source_obs.value if source_obs else None
            supply = target_obs.value if target_obs else None

            unknowns = []
            if demand is None:
                unknowns.append(f"{edge.source}.capacity")
            if supply is None:
                unknowns.append(f"{edge.target}.capacity")

            if demand is not None and supply is not None and supply > 0:
                value = demand / supply
            else:
                value = None

            inputs = []
            if source_obs:
                inputs.append(source_obs.id)
            if target_obs:
                inputs.append(target_obs.id)

            derivations.append(self._make_derivation(
                kind="constraint_pressure",
                subject=edge.id,
                value=value,
                unit="ratio",
                effective_at=snapshot.at,
                inputs=inputs,
                unknowns=unknowns,
            ))

        return derivations


# Keep backward-compatible function interface
def pressure(demand, supply):
    """Compute pressure ratio. Returns None if unknown, inf if supply<=0."""
    if demand is None or supply is None:
        return None
    if supply <= 0:
        return float("inf")
    return demand / supply


def severity(p):
    """Map pressure ratio to severity level."""
    if p is None:
        return "UNKNOWN"
    if p <= 1.0:
        return "NONE"
    if p <= 1.5:
        return "LOW"
    if p <= 2.0:
        return "MEDIUM"
    if p <= 3.0:
        return "HIGH"
    return "CRITICAL"


def classify(demand, supply):
    """Full classification of a demand/supply pair."""
    p = pressure(demand, supply)
    return {
        "pressure": p,
        "severity": severity(p),
        "demand": demand,
        "supply": supply,
    }
