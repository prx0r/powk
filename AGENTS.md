# AGENTS.md — POWKernel

## Scope Guard

Before adding anything to POWKernel ask:
**Does this reconstruct a dated dependency state or enable reproducible model execution?**

If no, it does not belong here.

## Explicitly Forbidden

- Domain-specific logic
- Economic constants or heuristic weights
- ML frameworks
- Collectors, APIs, dashboards
- Collectors, scrapers, LLMs
- Trading, portfolio, market assumptions
- Anything requiring `if domain == ...`

## How to Work

1. Read SPEC.md first.
2. All objects are NODE, EDGE, OBSERVATION, EVIDENCE, DERIVATION.
3. Edge relation is only REQUIRES.
4. Node IDs are domain-supplied, not content-addressed.
5. Record IDs ARE content-addressed.
6. Missing data is null.
7. Evidence != observation != derivation.
8. Same inputs must produce same outputs. Deterministic.
9. Models are versioned. Old outputs stay reproducible.
10. Counterfactuals create new snapshots, never mutate.

## How to Test

```bash
python3 -m pytest tests/ -v
```

Four fixtures cover four domains. If the kernel needs domain code to handle any of them,
the abstraction has failed.
