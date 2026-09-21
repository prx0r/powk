"""Unknowns reporting.

Reports which observations are absent from a snapshot.
Does NOT invent requirements — those come from the model.

Generic unknowns may report null fields already present,
but must not invent an economic checklist.
"""

from .snapshot import Snapshot


def unknowns(snapshot: Snapshot, requirements: list = None) -> list:
    """Report missing observations for each node.

    If requirements is provided, checks those specific (subject_kind, metric) pairs.
    Otherwise reports all observations with null values.

    Returns list of:
        {"node": node_id, "kind": node_kind, "label": node_label,
         "missing": [...], "present": [...]}
    """
    results = []

    for nid, node in snapshot.nodes.items():
        present = set()
        null_metrics = set()
        for obs in snapshot.observations_for(nid):
            if obs.value is not None:
                present.add(obs.metric)
            else:
                null_metrics.add(obs.metric)

        if requirements:
            # Check model-specific requirements
            missing = []
            for req in requirements:
                kind_match = req.get("subject_kind", "") == "" or req.get("subject_kind") == node.kind
                metric = req.get("metric", "")
                if kind_match and metric and metric not in present:
                    missing.append(metric)
        else:
            # Generic: report null metrics
            missing = sorted(null_metrics)

        if missing or present:
            results.append({
                "node": nid,
                "kind": node.kind,
                "label": node.label,
                "missing": missing,
                "present": sorted(present),
            })

    return results


def unknowns_for_node(snapshot: Snapshot, node_id: str, requirements: list = None) -> dict:
    """Get unknowns for a specific node."""
    node = snapshot.node(node_id)
    if not node:
        return {"node": node_id, "error": "not found"}

    present = set()
    null_metrics = set()
    for obs in snapshot.observations_for(node_id):
        if obs.value is not None:
            present.add(obs.metric)
        else:
            null_metrics.add(obs.metric)

    if requirements:
        missing = [r["metric"] for r in requirements
                   if (r.get("subject_kind", "") == "" or r.get("subject_kind") == node.kind)
                   and r["metric"] not in present]
    else:
        missing = sorted(null_metrics)

    return {
        "node": node_id,
        "kind": node.kind,
        "label": node.label,
        "missing": missing,
        "present": sorted(present),
    }


def summary(snapshot: Snapshot, requirements: list = None) -> dict:
    """Aggregate unknowns summary."""
    all_unknowns = unknowns(snapshot, requirements)
    total_missing = sum(len(u["missing"]) for u in all_unknowns)
    nodes_with_gaps = sum(1 for u in all_unknowns if u["missing"])
    return {
        "total_nodes": len(snapshot.nodes),
        "nodes_with_gaps": nodes_with_gaps,
        "total_missing_metrics": total_missing,
        "details": all_unknowns,
    }
