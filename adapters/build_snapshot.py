"""Build a real snapshot from exported garden data.

Loads JSONL exports from powpowpow and repair adapters,
merges them into a single Graph, and builds a dated snapshot.
"""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pow.graph import Graph
from pow.model import Node, Edge, Observation, Evidence
from pow.loader import load_jsonl
from pow.unknowns import summary
from pow.canonical import make_id


EXPORTS_DIR = Path(os.environ.get("POWK_EXPORT_DIR", "exports"))


def load_export(garden_name):
    """Load a garden's JSONL export into a Graph."""
    garden_dir = EXPORTS_DIR / garden_name
    if not garden_dir.exists():
        print(f"  Export not found: {garden_dir}")
        return Graph()

    g = Graph()
    for filename, cls in [
        ("nodes.jsonl", Node),
        ("edges.jsonl", Edge),
        ("observations.jsonl", Observation),
        ("evidence.jsonl", Evidence),
    ]:
        path = garden_dir / filename
        if path.exists():
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    obj = json.loads(line)
                    if cls == Node:
                        g.add(Node(**{k: obj[k] for k in ("id", "kind", "label") if k in obj}))
                    elif cls == Edge:
                        g.add(Edge(**{k: obj[k] for k in ("id", "source", "target", "relation") if k in obj}))
                    elif cls == Observation:
                        g.add(Observation(**{k: obj[k] for k in
                            ("id", "subject", "metric", "value", "unit",
                             "effective_at", "observed_at", "source_dataset") if k in obj}))
                    elif cls == Evidence:
                        g.add(Evidence(**{k: obj[k] for k in
                            ("id", "target", "direction", "claim",
                             "source_uri", "publisher", "published_at") if k in obj}))
    return g


def merge_graphs(*graphs):
    """Merge multiple graphs into one."""
    merged = Graph()
    for g in graphs:
        for node in g.nodes.values():
            merged.add(node)
        for edge in g.edges.values():
            merged.add(edge)
        for obs in g.observations:
            merged.add(obs)
        for ev in g.evidence.values():
            merged.add(ev)
    return merged


def main():
    print("Loading garden exports...")
    powpowpow_graph = load_export("powpowpow")
    print(f"  powpowpow: {powpowpow_graph.stats()}")

    repair_graph = load_export("repair")
    print(f"  repair: {repair_graph.stats()}")

    print("\nMerging...")
    merged = merge_graphs(powpowpow_graph, repair_graph)
    print(f"  merged: {merged.stats()}")

    print("\nBuilding snapshot...")
    snap = merged.build_snapshot("2026-09-21T00:00:00Z", mode="world")
    print(f"  nodes: {len(snap.nodes)}")
    print(f"  edges: {len(snap.edges)}")
    print(f"  observations: {len(snap.observations)}")
    print(f"  evidence: {len(snap.evidence)}")

    print("\nGraph traversal:")
    print(f"  roots: {snap.roots()[:5]}")
    print(f"  leaves: {snap.leaves()[:5]}")

    print("\nUnknowns:")
    u = summary(snap)
    print(f"  total_nodes: {u['total_nodes']}")
    print(f"  nodes_with_gaps: {u['nodes_with_gaps']}")
    print(f"  total_missing_metrics: {u['total_missing_metrics']}")

    # Show some observations
    print("\nSample observations:")
    for (subject, metric), obs in list(snap.observations.items())[:10]:
        print(f"  {subject}: {metric} = {obs.value} {obs.unit}")

    # Run pressure model
    print("\nRunning pressure model...")
    sys.path.insert(0, str(Path(__file__).parent.parent / "models" / "examples"))
    from pressure_v1 import PressureV1
    model = PressureV1()
    derivations = model.compute(snap)
    print(f"  Derivations: {len(derivations)}")
    for d in derivations[:5]:
        print(f"  {d.subject}: {d.value} ({d.unknowns})")

    return snap


if __name__ == "__main__":
    main()
