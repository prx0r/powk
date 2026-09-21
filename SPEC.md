# SPEC.md — POWKernel 0.2

> Deterministic Layer-2 substrate for reconstructing dated dependency states
> and running versioned models against them.

## Purpose

POWKernel reconstructs what we believed about a dependency network at any historical date,
and runs versioned models against that reconstruction.

It does not tell us what economics is true.

## Objects

Five canonical types. Nothing else exists in the kernel.

### NODE

A stable logical referent. IDs are domain-supplied, not content-addressed.

```json
{
  "id": "powuk:capability:soc2020:5241",
  "kind": "capability",
  "label": "Electricians and electrical fitters"
}
```

If the label changes, the entity persists.

### EDGE

A structural dependency: A REQUIRES B. Contains only the structural proposition
and optionally a coefficient.

```json
{
  "id": "edge:a1b2c3d4e5f6g7h8",
  "source": "powuk:data_centre",
  "target": "powuk:grid_connection",
  "relation": "REQUIRES",
  "coefficient": 1.0,
  "coefficient_unit": "MW/MW"
}
```

Time-varying properties (capacity, utilisation, lead_time) are OBSERVATIONs targeting this edge.

### OBSERVATION

A time-varying measurement. Bitemporal: effective_at and observed_at.

```json
{
  "id": "obs:x1y2z3w4a5b6c7d8",
  "subject": "powuk:transformer",
  "metric": "capacity",
  "value": 800,
  "unit": "units/yr",
  "effective_at": "2026-01-01T00:00:00Z",
  "observed_at": "2026-02-01T00:00:00Z",
  "source_dataset": "powflow:industry"
}
```

Observations can target nodes or edges.

### EVIDENCE

Why should I believe this record? Does not contain the numeric value.

```json
{
  "id": "ev:...",
  "target": "obs:...",
  "direction": "SUPPORTS",
  "claim": "NESO connection queue data",
  "publisher": "NESO",
  "published_at": "2026-01-10T00:00:00Z",
  "retrieved_at": "2026-01-15T00:00:00Z",
  "lineage_root": "neso:document:123",
  "content_hash": "sha256:..."
}
```

### DERIVATION

Computed output from a versioned model. Includes model identity and exact inputs
for reproducibility.

```json
{
  "id": "deriv:...",
  "kind": "constraint_pressure",
  "subject": "edge:...",
  "value": 0.84,
  "unit": "ratio",
  "effective_at": "2026-09-01T00:00:00Z",
  "model": "pressure/1.0.0",
  "model_hash": "a1b2c3d4e5f6g7h8",
  "inputs": ["obs:abc", "obs:def"],
  "unknowns": ["powuk:transformer.capacity"]
}
```

## Invariants

1. Layer-1 sources never depend on POWKernel.
2. Kernel knows no domain semantics.
3. Dependency direction is only A REQUIRES B.
4. Nodes have stable domain IDs; immutable records are content-addressed.
5. Edge structural state is separated from time-varying observations.
6. Missing data is null; unknown conclusions remain UNKNOWN.
7. Evidence, observation and inference are separate.
8. History is append-only.
9. World time and knowledge time are distinct.
10. Every model is versioned and identified by code hash.
11. Every derivation lists exact inputs.
12. Same snapshot + same model bytes = same derivation.
13. Counterfactuals create snapshots; they never mutate history.
14. Kernel topology contains no economic constants or heuristic weights.
15. A feature requiring domain-specific branching does not belong in the kernel.

## Operations

### Snapshot Building

```python
snapshot = graph.build_snapshot(at="2026-09-01", mode="world")
```

Reconstructs nodes, edges, observations, and evidence valid at time t.

### Graph Traversal

Pure topology, no economics:

```
upstream(node)      — what does this depend on?
downstream(node)    — what depends on this?
paths(a, b)         — all paths between nodes
roots()             — nodes with no incoming edges
leaves()            — nodes with no outgoing edges
```

### Counterfactuals

```python
scenario = snapshot.with_override(subject="transformer", metric="capacity", value=200)
result = model.compute(scenario)
```

Creates a new immutable snapshot. The original is never mutated.

### Unknowns

Reports missing observations for each node, driving the Layer 1 feedback loop.

### Model Interface

```python
class Model:
    name: str
    version: str
    model_hash: str  # SHA-256 of model code

    def required_inputs(self) -> list: ...
    def compute(snapshot: Snapshot) -> List[Derivation]: ...
```

## What is NOT in the kernel

- No collectors, APIs, websites, or scrapers
- No domain-specific logic (no electricians, transformers, GPUs, coins)
- No economic constants or heuristic weights
- No ML frameworks or dependencies
- No trading, portfolio, or market assumptions
- No dashboards, alerting, or monitoring
- No LLMs or research agents
- Stdlib Python only
