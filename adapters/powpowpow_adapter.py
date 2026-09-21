"""powpowpow adapter — export Layer 1 data to powk canonical format.

Reads from:
  chains/network_state.json  — live metrics per chain
  chains/chain_fundamentals.json — static chain config
  v1_registry.py — V1 universe definitions

Exports to powk JSONL:
  nodes.jsonl
  edges.jsonl
  observations.jsonl
  evidence.jsonl
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add powpowpow to path for imports
POWPOWPOW = Path("/home/ubuntu/powpowpow")
sys.path.insert(0, str(POWPOWPOW))

from pow.canonical import make_id
from pow.model import (
    Node, Edge, Observation, Evidence,
    make_edge_id, make_obs_id, make_ev_id,
)

EXPORT_DIR = Path("/home/ubuntu/powk/exports/powpowpow")


def load_json(path):
    with open(path) as f:
        return json.load(f)


def export_nodes():
    """Export V1 systems as NODEs."""
    nodes = []

    # V1 systems from registry
    try:
        from v1_registry import V1
        for symbol, info in V1.items():
            nid = f"powpowpow:network:{symbol.lower()}"
            nodes.append(Node(
                id=nid,
                kind="network",
                label=f"{symbol} Network",
            ))
    except ImportError:
        pass

    # Hardware entities from chain fundamentals
    fundamentals = load_json(POWPOWPOW / "chains" / "chain_fundamentals.json")
    if isinstance(fundamentals, dict):
        for symbol, info in fundamentals.items():
            if isinstance(info, dict):
                hw = info.get("hardware")
                if isinstance(hw, str) and hw and hw != "None":
                    hid = f"powpowpow:hardware:{hw.lower().replace(' ', '_').replace('/', '_')}"
                    nodes.append(Node(id=hid, kind="hardware", label=hw))
                elif isinstance(hw, list):
                    for h in hw:
                        if isinstance(h, str):
                            hid = f"powpowpow:hardware:{h.lower().replace(' ', '_')}"
                            nodes.append(Node(id=hid, kind="hardware", label=h))

    # Deduplicate
    seen = set()
    unique = []
    for n in nodes:
        if n.id not in seen:
            seen.add(n.id)
            unique.append(n)
    return unique


def export_edges(nodes):
    """Export REQUIRES edges between networks and their hardware dependencies."""
    edges = []
    node_ids = {n.id for n in nodes}

    try:
        from v1_registry import V1
        for symbol, info in V1.items():
            source_id = f"powpowpow:network:{symbol.lower()}"
            hw = info.get("hardware", [])
            if isinstance(hw, str) and hw:
                hw = [hw]
            if isinstance(hw, list):
                for h in hw:
                    target_id = f"powpowpow:hardware:{h.lower().replace(' ', '_').replace('/', '_')}"
                    if source_id in node_ids and target_id in node_ids:
                        edges.append(Edge(
                            id=make_edge_id(source_id, target_id),
                            source=source_id,
                            target=target_id,
                            relation="REQUIRES",
                        ))
    except ImportError:
        pass

    # Also add edges from chain fundamentals
    fundamentals = load_json(POWPOWPOW / "chains" / "chain_fundamentals.json")
    if isinstance(fundamentals, dict):
        for symbol, info in fundamentals.items():
            if not isinstance(info, dict):
                continue
            source_id = f"powpowpow:network:{symbol.lower()}"
            hw = info.get("hardware")
            if isinstance(hw, str) and hw and hw != "None":
                target_id = f"powpowpow:hardware:{hw.lower().replace(' ', '_').replace('/', '_')}"
                edge_key = (source_id, target_id)
                if source_id in node_ids and target_id in node_ids:
                    edges.append(Edge(
                        id=make_edge_id(source_id, target_id),
                        source=source_id,
                        target=target_id,
                        relation="REQUIRES",
                    ))

    return edges


def export_observations():
    """Export chain state as OBSERVATIONs."""
    observations = []
    now = datetime.now(timezone.utc).isoformat()

    network_state = load_json(POWPOWPOW / "chains" / "network_state.json")
    if not isinstance(network_state, dict):
        return observations

    for symbol, state in network_state.items():
        if not isinstance(state, dict):
            continue
        subject = f"powpowpow:network:{symbol.lower()}"
        effective = state.get("as_of", now)

        # Key metrics per chain
        metric_map = {
            "height": ("height", "blocks"),
            "network_hashrate": ("hashrate", "H/s"),
            "hashrate": ("hashrate", "H/s"),
            "difficulty": ("difficulty", "hash"),
            "tick_rate": ("tick_rate", "ticks/s"),
            "burn_rate": ("burn_rate", "ratio"),
            "daily_emission": ("daily_emission", "tokens/day"),
            "fee_per_kb": ("fee_per_kb", "units"),
            "p2pool_hashrate": ("p2pool_hashrate", "H/s"),
            "p2pool_miners": ("p2pool_miners", "people"),
            "total_transactions": ("total_transactions", "count"),
            "total_transfers": ("total_transfers", "count"),
            "epoch": ("epoch", "number"),
            "tick": ("tick", "number"),
        }

        for raw_metric, (metric, unit) in metric_map.items():
            value = state.get(raw_metric)
            if value is not None and isinstance(value, (int, float)):
                observations.append(Observation(
                    id=make_obs_id(subject, metric, effective, "powpowpow:network_state"),
                    subject=subject,
                    metric=metric,
                    value=float(value),
                    unit=unit,
                    effective_at=effective,
                    observed_at=now,
                    source_dataset="powpowpow:network_state",
                ))

    return observations


def export_evidence(observations):
    """Export evidence for observations."""
    evidence = []
    for obs in observations:
        ev_id = make_ev_id(obs.id, "SUPPORTS",
                           f"Chain state: {obs.subject} {obs.metric}={obs.value}",
                           "powpowpow")
        evidence.append(Evidence(
            id=ev_id,
            target=obs.id,
            direction="SUPPORTS",
            claim=f"Chain state observation: {obs.metric} = {obs.value} {obs.unit}",
            publisher="powpowpow",
            published_at=obs.observed_at,
            source_uri=f"powpowpow:chains/network_state",
        ))
    return evidence


def export(output_dir=None):
    """Run full export."""
    out = Path(output_dir) if output_dir else EXPORT_DIR
    out.mkdir(parents=True, exist_ok=True)

    print("Exporting powpowpow -> powk format...")

    nodes = export_nodes()
    print(f"  Nodes: {len(nodes)}")

    edges = export_edges(nodes)
    print(f"  Edges: {len(edges)}")

    observations = export_observations()
    print(f"  Observations: {len(observations)}")

    evidence = export_evidence(observations)
    print(f"  Evidence: {len(evidence)}")

    # Write JSONL
    for filename, items in [
        ("nodes.jsonl", nodes),
        ("edges.jsonl", edges),
        ("observations.jsonl", observations),
        ("evidence.jsonl", evidence),
    ]:
        path = out / filename
        with open(path, "w") as f:
            for item in items:
                f.write(json.dumps(item.to_dict(), default=str) + "\n")
        print(f"  Wrote {path}")

    return {"nodes": len(nodes), "edges": len(edges),
            "observations": len(observations), "evidence": len(evidence)}


if __name__ == "__main__":
    result = export()
    print(f"\nDone: {result}")
