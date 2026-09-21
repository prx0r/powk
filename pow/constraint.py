"""Constraint pressure — the core computation.

For each edge: demand / supply = pressure.
For each node: aggregate pressure across all edges.
"""
from __future__ import annotations
from typing import Optional
from .graph import Graph
from .model import Derivation, Observation


def edge_pressure(graph: Graph, edge) -> Optional[dict]:
    """Compute pressure for a single edge.
    
    Returns dict with pressure, unknowns, or None if insufficient data.
    """
    supply_obs = graph.get_observation(edge.target, "capacity")
    demand_obs = graph.get_observation(edge.source, "capacity")
    
    # Also try demand from the edge itself
    if demand_obs is None:
        demand_obs = graph.get_observation(edge.source, "demand")
    
    unknowns = []
    
    supply = None
    if supply_obs and supply_obs.value is not None:
        supply = supply_obs.value
    else:
        unknowns.append(f"capacity:{edge.target}")
    
    demand = None
    if demand_obs and demand_obs.value is not None:
        demand = demand_obs.value
    elif edge.supply.get("capacity") is not None:
        # Use edge-level supply data as fallback
        supply = edge.supply["capacity"]
    else:
        unknowns.append(f"demand:{edge.source}")
    
    if unknowns:
        return {"pressure": None, "unknowns": unknowns, "demand": demand, "supply": supply}
    
    if supply is None or supply <= 0:
        return {"pressure": float("inf"), "unknowns": [], "demand": demand, "supply": supply}
    
    return {"pressure": demand / supply, "unknowns": [], "demand": demand, "supply": supply}


def constraint_pressure(graph: Graph) -> list[Derivation]:
    """Compute constraint pressure for all edges.
    
    Returns list of Derivation objects.
    """
    derivations = []
    
    for edge in graph.edges.values():
        result = edge_pressure(graph, edge)
        if result is None:
            continue
        
        inputs = []
        for obs in graph.observations_for(edge.source):
            inputs.append(obs.id)
        for obs in graph.observations_for(edge.target):
            inputs.append(obs.id)
        
        d = Derivation.create(
            kind="constraint_pressure",
            subject=edge.id,
            value=result["pressure"],
            as_of="2026-09-21",  # would use latest observation date in production
            model="constraint_pressure/v1",
            inputs=inputs,
            unknowns=result["unknowns"],
        )
        derivations.append(d)
    
    return derivations


def node_pressure(graph: Graph) -> dict[str, Optional[float]]:
    """Compute aggregate pressure for each node.
    
    For nodes with outgoing REQUIRES edges: average of edge pressures.
    For leaf nodes: None (no dependencies to measure).
    """
    node_pressures = {}
    
    for node in graph.nodes.values():
        outgoing = graph.requires(node.id)
        if not outgoing:
            node_pressures[node.id] = None
            continue
        
        pressures = []
        for edge in outgoing:
            result = edge_pressure(graph, edge)
            if result and result["pressure"] is not None:
                pressures.append(result["pressure"])
        
        if pressures:
            node_pressures[node.id] = sum(pressures) / len(pressures)
        else:
            node_pressures[node.id] = None
    
    return node_pressures


def bottlenecks(graph: Graph, threshold: float = 2.0) -> list[dict]:
    """Find edges where pressure exceeds threshold."""
    results = []
    for edge in graph.edges.values():
        result = edge_pressure(graph, edge)
        if result and result["pressure"] is not None and result["pressure"] >= threshold:
            results.append({
                "edge": edge.to_dict(),
                "pressure": result["pressure"],
                "demand": result["demand"],
                "supply": result["supply"],
            })
    return sorted(results, key=lambda x: x["pressure"], reverse=True)
