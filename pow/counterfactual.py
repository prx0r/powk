"""Counterfactual simulation — shock, propagate, relieve.

What happens if something changes?
"""
from __future__ import annotations
from typing import Optional
from .graph import Graph
from .model import Derivation
from .constraint import edge_pressure


def shock(graph: Graph, node_id: str, delta: float, metric: str = "capacity") -> list[Derivation]:
    """Simulate a shock to a node (e.g. capacity doubles).
    
    delta: multiplicative factor (2.0 = double, 0.5 = halve)
    Returns new derivations showing impact cascade.
    """
    derivations = []
    
    # Get current observation for this node
    current = graph.get_observation(node_id, metric)
    if current is None or current.value is None:
        return [Derivation.create(
            kind="shock",
            subject=node_id,
            value=None,
            as_of="shock",
            model="shock/v1",
            unknowns=[f"no baseline observation for {node_id}:{metric}"],
        )]
    
    new_value = current.value * delta
    
    # Propagate downstream
    downstream = graph.downstream(node_id)
    
    for nid in downstream:
        # For each downstream node, recompute pressure on edges
        for edge in graph.requires(nid):
            result = edge_pressure(graph, edge)
            if result and result["pressure"] is not None:
                d = Derivation.create(
                    kind="shock_impact",
                    subject=edge.id,
                    value=result["pressure"],
                    as_of="shock",
                    model="shock/v1",
                    inputs=[current.id],
                )
                derivations.append(d)
    
    return derivations


def propagate(graph: Graph, node_id: str) -> dict:
    """What is affected if this node changes?"""
    downstream = graph.downstream(node_id)
    upstream = graph.upstream(node_id)
    
    return {
        "node": node_id,
        "downstream_affected": downstream,
        "upstream_dependencies": upstream,
        "downstream_count": len(downstream),
        "upstream_count": len(upstream),
    }


def relieve(graph: Graph, edge_id: str) -> list[dict]:
    """What alternatives exist for a constraint?
    
    Look for edges with same source that have different targets.
    """
    edge = graph.edge(edge_id)
    if edge is None:
        return []
    
    alternatives = []
    for other in graph.edges.values():
        if other.source == edge.source and other.id != edge_id:
            alternatives.append(other.to_dict())
    
    return alternatives


def criticality(graph: Graph) -> list[dict]:
    """Which nodes are structurally critical?
    
    Criticality = number of downstream dependents * average upstream pressure.
    """
    scores = []
    for node in graph.nodes.values():
        downstream_count = len(graph.downstream(node.id))
        outgoing = graph.requires(node.id)
        
        pressures = []
        for edge in outgoing:
            result = edge_pressure(graph, edge)
            if result and result["pressure"] is not None:
                pressures.append(result["pressure"])
        
        avg_pressure = sum(pressures) / len(pressures) if pressures else 0
        score = downstream_count * max(avg_pressure, 1)
        
        scores.append({
            "node": node.to_dict(),
            "downstream_count": downstream_count,
            "avg_pressure": avg_pressure,
            "criticality_score": score,
        })
    
    return sorted(scores, key=lambda x: x["criticality_score"], reverse=True)


def unknowns(graph: Graph) -> list[dict]:
    """What data is missing?
    
    For each edge, check what observations are needed but absent.
    """
    missing = []
    for edge in graph.edges.values():
        result = edge_pressure(graph, edge)
        if result and result["unknowns"]:
            missing.append({
                "edge": edge.to_dict(),
                "missing": result["unknowns"],
            })
    return missing
