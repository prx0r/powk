"""Core data model — five canonical types.

POWKernel knows only:
  NODE      — stable logical referent
  EDGE      — A REQUIRES B (structural only)
  OBSERVATION — time-varying measurement
  EVIDENCE  — why we believe a record
  DERIVATION — computed output from a model

Invariants:
  - Node IDs are stable domain-supplied (not content-addressed)
  - Record IDs (obs, ev, deriv) ARE content-addressed
  - Edge contains only structural dependency + coefficient
  - All time-varying data lives in Observation
  - Missing data is null; never zero or placeholder
"""

from dataclasses import dataclass, field
from typing import Optional

from .canonical import make_id, content_id


@dataclass(frozen=True)
class Node:
    """A stable logical referent in the dependency graph.

    Node IDs are supplied by the domain (e.g. "powuk:capability:5241"),
    NOT content-addressed. If the label changes, the entity persists.
    """
    id: str
    kind: str  # capability, equipment, resource, component, capacity
    label: str
    valid_from: Optional[str] = None  # ISO date when this node definition became valid
    valid_to: Optional[str] = None    # ISO date when it was superseded (None = still valid)

    def to_dict(self) -> dict:
        d = {"id": self.id, "kind": self.kind, "label": self.label}
        if self.valid_from:
            d["valid_from"] = self.valid_from
        if self.valid_to:
            d["valid_to"] = self.valid_to
        return d


@dataclass(frozen=True)
class Edge:
    """A structural dependency: A REQUIRES B.

    Contains only the structural proposition and optionally a coefficient.
    All time-varying properties (capacity, utilisation, lead_time, etc.)
    are OBSERVATIONs targeting this edge.
    """
    id: str
    source: str  # node.id (the dependent)
    target: str  # node.id (the dependency)
    relation: str  # only "REQUIRES"
    coefficient: Optional[float] = None
    coefficient_unit: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "source": self.source,
            "target": self.target,
            "relation": self.relation,
        }
        if self.coefficient is not None:
            d["coefficient"] = self.coefficient
        if self.coefficient_unit is not None:
            d["coefficient_unit"] = self.coefficient_unit
        if self.valid_from:
            d["valid_from"] = self.valid_from
        if self.valid_to:
            d["valid_to"] = self.valid_to
        return d


@dataclass(frozen=True)
class Observation:
    """A time-varying measurement targeting a node or edge.

    Bitemporal: effective_at (when it was true in the world)
                observed_at  (when we learned it)
    """
    id: str
    subject: str  # node.id or edge.id
    metric: str
    value: Optional[float]
    unit: Optional[str]
    effective_at: str  # ISO timestamp — when this was true in reality
    observed_at: str   # ISO timestamp — when we recorded it
    source_dataset: str  # where this observation came from

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "subject": self.subject,
            "metric": self.metric,
            "value": self.value,
            "unit": self.unit,
            "effective_at": self.effective_at,
            "observed_at": self.observed_at,
            "source_dataset": self.source_dataset,
        }
        return d


@dataclass(frozen=True)
class Evidence:
    """Why should I believe this record?

    Evidence supports, quantifies, or contradicts an observation or edge.
    Does NOT contain the numeric value — that lives in the Observation.
    """
    id: str
    target: str  # observation.id or edge.id
    direction: str  # SUPPORTS, QUANTIFIES, CONTRADICTS
    claim: str
    source_uri: Optional[str] = None
    publisher: Optional[str] = None
    published_at: Optional[str] = None
    retrieved_at: Optional[str] = None
    lineage_root: Optional[str] = None
    content_hash: Optional[str] = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "target": self.target,
            "direction": self.direction,
            "claim": self.claim,
        }
        for k in ("source_uri", "publisher", "published_at", "retrieved_at",
                   "lineage_root", "content_hash"):
            v = getattr(self, k)
            if v is not None:
                d[k] = v
        return d


@dataclass(frozen=True)
class Derivation:
    """Computed output from a versioned model.

    ID includes model identity + inputs for reproducibility:
      same model bytes + same input bytes = same derivation ID
    """
    id: str
    kind: str
    subject: str
    value: Optional[float]
    unit: Optional[str]
    effective_at: str
    model: str        # e.g. "pressure/v1"
    model_hash: str   # SHA-256 of model code
    inputs: list = field(default_factory=list)  # IDs of input observations/edges
    unknowns: list = field(default_factory=list)  # names of missing data

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "kind": self.kind,
            "subject": self.subject,
            "value": self.value,
            "unit": self.unit,
            "effective_at": self.effective_at,
            "model": self.model,
            "model_hash": self.model_hash,
            "inputs": self.inputs,
        }
        if self.unknowns:
            d["unknowns"] = self.unknowns
        return d


# ─── Factory helpers ──────────────────────────────────────────

def make_edge_id(source: str, target: str, relation: str = "REQUIRES") -> str:
    """Edge ID from structural proposition (content-addressed)."""
    return make_id("edge", {"source": source, "target": target, "relation": relation})


def make_obs_id(subject: str, metric: str, effective_at: str, source_dataset: str) -> str:
    """Observation ID from its identity fields (content-addressed)."""
    return make_id("obs", {"subject": subject, "metric": metric,
                           "effective_at": effective_at, "source_dataset": source_dataset})


def make_ev_id(target: str, direction: str, claim: str, publisher: str = "") -> str:
    """Evidence ID (content-addressed)."""
    return make_id("ev", {"target": target, "direction": direction,
                          "claim": claim, "publisher": publisher})


def make_deriv_id(kind: str, subject: str, model: str, model_hash: str,
                  effective_at: str, inputs: list) -> str:
    """Derivation ID — includes model identity + inputs for reproducibility."""
    return make_id("deriv", {
        "kind": kind, "subject": subject, "model": model,
        "model_hash": model_hash, "effective_at": effective_at,
        "inputs": sorted(inputs),
    })
