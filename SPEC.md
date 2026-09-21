# SPEC.md — POW/0.1

> The constraint interchange format for dependency networks.

---

## Question

Given evidence about a dependency network changing through time, what is constrained, why, how strongly, and what happens if something changes?

---

## Objects

### NODE

Something whose capacity or state might matter.

```json
{
  "id": "string (content-addressed)",
  "kind": "capability | equipment | resource | skill | component | capacity",
  "label": "string"
}
```

### EDGE

A dependency. Direction is strict: A REQUIRES B means A cannot scale without B.

```json
{
  "id": "string (content-addressed)",
  "source": "node.id",
  "target": "node.id",
  "relation": "REQUIRES",
  "requirement": {
    "quantity_per_unit": "float | null",
    "unit": "string | null"
  },
  "supply": {
    "capacity": "float | null",
    "utilisation": "float | null",
    "growth_rate": "float | null",
    "lead_time_days": "float | null"
  },
  "substitution": {
    "substitutability": "float 0-1 | null",
    "switching_cost": "float | null"
  },
  "timing": {
    "needed_by": "ISO date | null",
    "capacity_available_by": "ISO date | null"
  }
}
```

### OBSERVATION

Something we actually measured.

```json
{
  "id": "string (content-addressed)",
  "metric": "string",
  "subject": "node.id | edge.id",
  "value": "float | null",
  "unit": "string | null",
  "as_of": "ISO date",
  "source": "string"
}
```

Missing = `null`. Never `0`, never `"probably"`.

### EVIDENCE

Supports an observation or dependency. Three articles repeating one manufacturer statement are one source, not three.

```json
{
  "id": "string (content-addressed)",
  "claim": "string",
  "target": "observation.id | edge.id",
  "direction": "QUANTIFIES | SUPPORTS | CONTRADICTS",
  "source_uri": "string | null",
  "publisher": "string | null",
  "published_at": "ISO date | null",
  "observed_at": "ISO date",
  "lineage_root": "string | null",
  "value": "float | null",
  "unit": "string | null"
}
```

### DERIVATION

Computed state. Never overwrites evidence.

```json
{
  "id": "string (content-addressed)",
  "kind": "string",
  "subject": "node.id | edge.id",
  "value": "float | null",
  "as_of": "ISO date",
  "model": "string (versioned)",
  "inputs": ["obs:...", "edge:..."],
  "unknowns": ["string"]
}
```

---

## Rules

1. **Direction**: A REQUIRES B. That is the only edge type initially.
2. **Unknown = null**: Missing data is null, never zero or estimated silently.
3. **Append-only**: Never rewrite history. Append new observations.
4. **Evidence ≠ inference**: Source evidence and computed derivations are different objects.
5. **Content-addressed IDs**: `id = sha256(canonical(object))`. Same inputs = same ID.
6. **Versioned models**: If the model changes, create a new version. Old outputs remain reproducible.
7. **Replayable**: Any derivation can be recomputed from its inputs.

---

## Forbidden in the kernel

collectors, UK-specific logic, APIs, dashboards, trading, agents, tasks, grants, permissions, cryptographic signatures, belief models, autonomous execution, scrapers, LLM research agents.

---

## Transforms

Six pure functions over the graph:

```
constraint(graph, observations)  → derivations
propagate(graph, shock)          → affected nodes
relieve(graph, bottleneck)       → alternative paths
shock(graph, node, delta)        → propagation cascade
criticality(graph)               → node criticality scores
unknowns(graph, observations)    → missing data map
```

---

## Storage

Append-only JSONL. One line per object. Content-addressed filenames.

```
store/
  nodes/
  edges/
  observations/
  evidence/
  derivations/
```

---

## Models

```
models/
  pressure_v1.py    demand/supply ratio
  seesaw_v1.py      MDTP/CA (research hypothesis, not truth)
```

All consume the same evidence snapshot. All output derivations. Historical data tells us which predicts.

---

*This spec is the truth. Implementations validate against it.*
