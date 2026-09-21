# AGENTS.md — powkernel operations

> A minimal kernel for constraint interchange across dependency networks.

---

## Scope guard

**Before adding anything to POWKernel ask: does this improve our ability to represent, quantify, propagate, falsify, or replay a physical/economic constraint? If no, it does not belong here.**

### Forbidden in the kernel

```
collectors
UK-specific logic
stock-specific logic
repair-specific logic
crypto-specific logic
APIs
dashboards
trading
news
company resolution
product catalogs
scrapers
LLM research agents
agents
tasks
grants
permissions
cryptographic signatures
tournaments
belief models
trading states
autonomous execution
```

### Belongs in the POWs, not the kernel

```
electricians, apprenticeships, planning (→ POWUK)
parts, models, failures (→ Repair)
securities, directors, ownership (→ POWStocks)
materials, factories, logistics (→ POWFlow)
```

---

## The four objects

```text
NODE     — something whose capacity/state might matter
EDGE     — A REQUIRES B (the only relation initially)
OBSERVATION — something we actually measured
EVIDENCE    — supports an observation or dependency
```

And one output:

```text
DERIVATION  — computed state, never overwrites evidence
```

---

## The six transforms

```text
constraint()   — what binds?
propagate()    — what is affected?
relieve()      — what alternatives exist?
shock()        — what happens if X changes?
criticality()  — which node matters most?
unknowns()     — what data is missing?
```

---

## The rules

1. **Direction**: A REQUIRES B. That is the only edge type initially.
2. **Unknown = null**: Missing data is null, never zero or estimated silently.
3. **Append-only**: Never rewrite history. Append new observations.
4. **Evidence ≠ inference**: Source evidence and computed derivations are different objects.
5. **Content-addressed IDs**: `id = sha256(canonical(object))`. Same inputs = same ID.
6. **Versioned models**: If the model changes, create a new version. Old outputs remain reproducible.
7. **Replayable**: Any derivation can be recomputed from its inputs.

---

## How to operate

### Run tests
```bash
cd /root/k2
python3 -m pytest tests/ -v
```

### Run example
```bash
python3 -c "
from pow.graph import Graph
from pow.constraint import constraint_pressure
import json

g = Graph()
g.load_fixture('examples/uk_grid.json')
for d in constraint_pressure(g):
    print(json.dumps(d, indent=2))
"
```

---

## Repository structure

```
k2/
├── SPEC.md           — the POW/0.1 protocol
├── AGENTS.md         — this file
├── pow/
│   ├── __init__.py
│   ├── canonical.py  — content-addressed IDs, canonical forms
│   ├── model.py      — NODE, EDGE, OBSERVATION, EVIDENCE, DERIVATION
│   ├── evidence.py   — evidence validation, dedup, lineage
│   ├── graph.py      — graph operations, traversal, dependency walk
│   ├── constraint.py — constraint pressure, propagation
│   ├── counterfactual.py — shock simulation, what-if
│   └── store.py      — append-only JSONL store
├── models/
│   ├── __init__.py
│   ├── pressure_v1.py
│   └── seesaw_v1.py
├── examples/
│   ├── uk_grid.json
│   ├── repair.json
│   └── compute.json
└── tests/
    ├── __init__.py
    └── test_kernel.py
```

---

## The three test fixtures

```text
UK GRID
  data_centres → grid_connections → transformers → electrical_steel

REPAIR
  inverter → capacitor → replacement_part → technician_skill

COMPUTE
  AI_inference → GPUs → HBM → fabs
```

If the same kernel answers all three without domain-specific code, POWKernel is real.
