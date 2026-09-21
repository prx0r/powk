"""Seesaw v1 — research hypothesis, not truth.

S_i = (M * D * T) / (C * A)

Where:
  M = market size
  D = demand growth
  T = technology complexity
  C = capacity response
  A = entry attractiveness

This is a HYPOTHESIS. It may not predict real outcomes.
All models compete on the same evidence. Historical data decides.
"""
from __future__ import annotations
from typing import Optional


def seesaw(
    market_size: Optional[float] = None,
    demand_growth: Optional[float] = None,
    tech_complexity: Optional[float] = None,
    capacity_response: Optional[float] = None,
    entry_attractiveness: Optional[float] = None,
) -> dict:
    """Compute seesaw score.
    
    Returns score and missing inputs.
    All inputs should be 0-1 normalized.
    """
    inputs = {
        "M": market_size,
        "D": demand_growth,
        "T": tech_complexity,
        "C": capacity_response,
        "A": entry_attractiveness,
    }
    
    missing = [k for k, v in inputs.items() if v is None]
    
    if missing:
        return {"score": None, "missing": missing, "inputs": inputs}
    
    denominator = capacity_response * entry_attractiveness
    if denominator <= 0:
        return {"score": float("inf"), "missing": [], "inputs": inputs}
    
    score = (market_size * demand_growth * tech_complexity) / denominator
    
    return {"score": score, "missing": [], "inputs": inputs}
