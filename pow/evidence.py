"""Evidence validation, dedup, and lineage.

Three articles repeating one manufacturer statement are one source, not three.
"""
from __future__ import annotations
from typing import Optional
from .model import Evidence


def dedup_evidence(evidences: list[Evidence]) -> list[Evidence]:
    """Deduplicate evidence by (target, direction, value, publisher).
    
    Same claim from different URIs about the same thing = one piece of evidence.
    """
    seen = {}
    for ev in evidences:
        key = (ev.target, ev.direction, ev.value, ev.publisher)
        if key not in seen:
            seen[key] = ev
    return list(seen.values())


def validate_evidence(ev: Evidence) -> list[str]:
    """Validate evidence structure. Returns list of errors (empty = valid)."""
    errors = []
    if not ev.claim:
        errors.append("claim is required")
    if not ev.target:
        errors.append("target is required")
    if ev.direction not in ("QUANTIFIES", "SUPPORTS", "CONTRADICTS"):
        errors.append(f"direction must be QUANTIFIES|SUPPORTS|CONTRADICTS, got {ev.direction}")
    if not ev.observed_at:
        errors.append("observed_at is required")
    return errors


def chain_lineage(evidences: list[Evidence]) -> dict[str, list[str]]:
    """Build lineage chains. Returns {root_id: [child_ids]}."""
    chains = {}
    for ev in evidences:
        root = ev.lineage_root or ev.id
        chains.setdefault(root, []).append(ev.id)
    return chains


def conflicting_evidence(evidences: list[Evidence]) -> list[tuple[Evidence, Evidence]]:
    """Find pairs of evidence that CONTRADICT each other on the same target."""
    by_target = {}
    for ev in evidences:
        by_target.setdefault(ev.target, []).append(ev)
    
    conflicts = []
    for target, evs in by_target.items():
        quants = [e for e in evs if e.direction == "QUANTIFIES"]
        contras = [e for e in evs if e.direction == "CONTRADICTS"]
        for q in quants:
            for c in contras:
                conflicts.append((q, c))
    return conflicts
