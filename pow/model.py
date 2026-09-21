"""The five canonical objects.

NODE, EDGE, OBSERVATION, EVIDENCE, DERIVATION.

Nothing else belongs in the kernel.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Optional

from .canonical import content_id, make_id


# ─── NODE ────────────────────────────────────────────────────

@dataclass(frozen=True)
class Node:
    id: str
    kind: str  # capability | equipment | resource | skill | component | capacity
    label: str

    @staticmethod
    def create(kind: str, label: str, id_override: str = None) -> Node:
        raw = {"kind": kind, "label": label}
        nid = id_override or make_id("node", raw)
        return Node(id=nid, kind=kind, label=label)

    def to_dict(self) -> dict:
        return {"id": self.id, "kind": self.kind, "label": self.label}


# ─── EDGE ────────────────────────────────────────────────────

@dataclass(frozen=True)
class Edge:
    id: str
    source: str  # node.id
    target: str  # node.id
    relation: str  # "REQUIRES" — the only type initially
    requirement: dict = field(default_factory=dict)
    supply: dict = field(default_factory=dict)
    substitution: dict = field(default_factory=dict)
    timing: dict = field(default_factory=dict)

    @staticmethod
    def create(source: str, target: str, **kw) -> Edge:
        raw = {"source": source, "target": target, "relation": "REQUIRES", **kw}
        eid = make_id("edge", raw)
        return Edge(id=eid, source=source, target=target, relation="REQUIRES",
                    requirement=kw.get("requirement", {}),
                    supply=kw.get("supply", {}),
                    substitution=kw.get("substitution", {}),
                    timing=kw.get("timing", {}))

    def to_dict(self) -> dict:
        d = {"id": self.id, "source": self.source, "target": self.target,
             "relation": self.relation}
        if self.requirement: d["requirement"] = self.requirement
        if self.supply: d["supply"] = self.supply
        if self.substitution: d["substitution"] = self.substitution
        if self.timing: d["timing"] = self.timing
        return d


# ─── OBSERVATION ─────────────────────────────────────────────

@dataclass(frozen=True)
class Observation:
    id: str
    metric: str
    subject: str  # node.id or edge.id
    value: Optional[float]
    unit: Optional[str]
    as_of: str  # ISO date
    source: str

    @staticmethod
    def create(metric: str, subject: str, value: Optional[float],
               unit: Optional[str], as_of: str, source: str) -> Observation:
        raw = {"metric": metric, "subject": subject, "value": value,
               "unit": unit, "as_of": as_of, "source": source}
        oid = make_id("obs", raw)
        return Observation(id=oid, metric=metric, subject=subject,
                          value=value, unit=unit, as_of=as_of, source=source)

    def to_dict(self) -> dict:
        return {"id": self.id, "metric": self.metric, "subject": self.subject,
                "value": self.value, "unit": self.unit, "as_of": self.as_of,
                "source": self.source}


# ─── EVIDENCE ────────────────────────────────────────────────

@dataclass(frozen=True)
class Evidence:
    id: str
    claim: str
    target: str  # observation.id or edge.id
    direction: str  # QUANTIFIES | SUPPORTS | CONTRADICTS
    source_uri: Optional[str] = None
    publisher: Optional[str] = None
    published_at: Optional[str] = None
    observed_at: str = ""
    lineage_root: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None

    @staticmethod
    def create(claim: str, target: str, direction: str, **kw) -> Evidence:
        raw = {"claim": claim, "target": target, "direction": direction, **kw}
        eid = make_id("ev", raw)
        return Evidence(id=eid, claim=claim, target=target, direction=direction, **kw)

    def to_dict(self) -> dict:
        d = {"id": self.id, "claim": self.claim, "target": self.target,
             "direction": self.direction, "observed_at": self.observed_at}
        for k in ("source_uri", "publisher", "published_at", "lineage_root", "value", "unit"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        return d


# ─── DERIVATION ──────────────────────────────────────────────

@dataclass(frozen=True)
class Derivation:
    id: str
    kind: str
    subject: str  # node.id or edge.id
    value: Optional[float]
    as_of: str
    model: str  # versioned, e.g. "constraint_pressure/v1"
    inputs: list = field(default_factory=list)
    unknowns: list = field(default_factory=list)

    @staticmethod
    def create(kind: str, subject: str, value: Optional[float],
               as_of: str, model: str, inputs: list = None,
               unknowns: list = None) -> Derivation:
        raw = {"kind": kind, "subject": subject, "value": value,
               "as_of": as_of, "model": model}
        did = make_id("deriv", raw)
        return Derivation(id=did, kind=kind, subject=subject, value=value,
                         as_of=as_of, model=model,
                         inputs=inputs or [], unknowns=unknowns or [])

    def to_dict(self) -> dict:
        d = {"id": self.id, "kind": self.kind, "subject": self.subject,
             "value": self.value, "as_of": self.as_of, "model": self.model,
             "inputs": self.inputs}
        if self.unknowns:
            d["unknowns"] = self.unknowns
        return d
