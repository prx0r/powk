"""Seesaw v1 — research hypothesis model.

Computes: (market_concentration * demand_growth * tech_lockin) /
          (capacity_headroom * alternative_availability)

EXPLICITLY labeled as a research hypothesis, not established truth.
Missing factors default to 1.0 (neutral).

This is a MODEL, not kernel truth.
"""

from typing import List

from pow.model_base import Model
from pow.snapshot import Snapshot
from pow.model import Derivation


class SeesawV1(Model):
    name = "seesaw"
    version = "1.0.0"

    def requirements(self, snapshot=None):
        return [
            {"subject_kind": "any", "metric": "market_concentration"},
            {"subject_kind": "any", "metric": "demand_growth"},
            {"subject_kind": "any", "metric": "tech_lockin"},
            {"subject_kind": "any", "metric": "capacity_headroom"},
            {"subject_kind": "any", "metric": "alternative_availability"},
        ]

    def compute(self, snapshot: Snapshot) -> List[Derivation]:
        derivations = []
        for node in snapshot.nodes.values():
            factors = {}
            missing = []

            for metric in ("market_concentration", "demand_growth", "tech_lockin",
                           "capacity_headroom", "alternative_availability"):
                obs = snapshot.observation(node.id, metric)
                if obs and obs.value is not None:
                    factors[metric] = obs.value
                else:
                    missing.append(metric)
                    factors[metric] = 1.0  # neutral default

            numerator = factors["market_concentration"] * factors["demand_growth"] * factors["tech_lockin"]
            denominator = factors["capacity_headroom"] * factors["alternative_availability"]

            if denominator > 0:
                value = numerator / denominator
            elif denominator == 0 and numerator == 0:
                value = 0.0
            else:
                value = float("inf")

            inputs = []
            for metric in ("market_concentration", "demand_growth", "tech_lockin",
                           "capacity_headroom", "alternative_availability"):
                obs = snapshot.observation(node.id, metric)
                if obs:
                    inputs.append(obs.id)

            derivations.append(self._make_derivation(
                kind="seesaw_score",
                subject=node.id,
                value=value,
                unit="score",
                effective_at=snapshot.at,
                inputs=inputs,
                unknowns=missing,
            ))

        return derivations


def seesaw(M, D, T, C, A):
    """Direct seesaw computation. Returns dict with score and missing inputs."""
    missing = []
    factors = {}
    for name, val in [("M", M), ("D", D), ("T", T), ("C", C), ("A", A)]:
        if val is None:
            missing.append(name)
            factors[name] = 1.0
        else:
            factors[name] = val

    num = factors["M"] * factors["D"] * factors["T"]
    den = factors["C"] * factors["A"]

    if den > 0:
        score = num / den
    elif den == 0 and num == 0:
        score = 0.0
    else:
        score = float("inf")

    return {"score": score, "missing": missing, "inputs": factors}
