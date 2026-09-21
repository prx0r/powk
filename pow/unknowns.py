"""Explicit unknown tracking.

For each node in a snapshot, reports which standard metrics
have no observation. This drives the Layer 1 → Layer 2 feedback loop.
"""

from .snapshot import Snapshot


# Standard metrics per node kind that a model might need
REQUIRED_METRICS = {
    "capability": ["capacity", "utilisation"],
    "equipment": ["capacity", "lead_time"],
    "resource": ["capacity", "growth_rate"],
    "component": ["capacity"],
    "capacity": ["capacity", "utilisation"],
}


def unknowns(snapshot: Snapshot, required: dict = None) -> list:
    """Report what data is missing for each node.

    Returns list of:
        {"node": node_id, "missing": ["metric1", "metric2"], "present": ["metric3"]}
    """
    required = required or REQUIRED_METRICS
    results = []

    for nid, node in snapshot.nodes.items():
        kind_metrics = required.get(node.kind, [])
        present = set()
        for obs in snapshot.observations_for(nid):
            present.add(obs.metric)

        missing = [m for m in kind_metrics if m not in present]
        if missing or kind_metrics:
            results.append({
                "node": nid,
                "kind": node.kind,
                "label": node.label,
                "missing": missing,
                "present": sorted(present),
            })

    return results


def unknowns_for_node(snapshot: Snapshot, node_id: str) -> dict:
    """Get unknowns for a specific node."""
    node = snapshot.node(node_id)
    if not node:
        return {"node": node_id, "error": "not found"}

    kind_metrics = REQUIRED_METRICS.get(node.kind, [])
    present = {obs.metric for obs in snapshot.observations_for(node_id)}
    missing = [m for m in kind_metrics if m not in present]

    return {
        "node": node_id,
        "kind": node.kind,
        "label": node.label,
        "missing": missing,
        "present": sorted(present),
    }


def summary(snapshot: Snapshot) -> dict:
    """Aggregate unknowns summary."""
    all_unknowns = unknowns(snapshot)
    total_missing = sum(len(u["missing"]) for u in all_unknowns)
    nodes_with_gaps = sum(1 for u in all_unknowns if u["missing"])
    return {
        "total_nodes": len(snapshot.nodes),
        "nodes_with_gaps": nodes_with_gaps,
        "total_missing_metrics": total_missing,
        "details": all_unknowns,
    }
