"""Constraint pressure v1.

Simple demand/supply ratio. The most basic constraint metric.

pressure = demand / supply

pressure > 3.0 = CRITICAL
pressure > 2.0 = HIGH
pressure > 1.5 = MEDIUM
pressure > 1.0 = LOW
pressure <= 1.0 = NONE
"""
from __future__ import annotations
from enum import IntEnum
from typing import Optional


class Severity(IntEnum):
    NONE = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


def pressure(demand: Optional[float], supply: Optional[float]) -> Optional[float]:
    """Compute demand/supply ratio."""
    if demand is None or supply is None:
        return None
    if supply <= 0:
        return float("inf")
    return demand / supply


def severity(p: Optional[float]) -> Severity:
    """Map pressure to severity level."""
    if p is None:
        return Severity.NONE
    if p > 3.0:
        return Severity.CRITICAL
    if p > 2.0:
        return Severity.HIGH
    if p > 1.5:
        return Severity.MEDIUM
    if p > 1.0:
        return Severity.LOW
    return Severity.NONE


def classify(demand: Optional[float], supply: Optional[float]) -> dict:
    """Full classification of a demand/supply pair."""
    p = pressure(demand, supply)
    s = severity(p)
    return {
        "pressure": p,
        "severity": s.name,
        "severity_value": int(s),
        "demand": demand,
        "supply": supply,
    }
