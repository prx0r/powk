"""Graph operations — traversal, dependency walk, reverse dependency walk.

The graph is the core data structure. Everything operates over it.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Optional
from .model import Node, Edge, Observation, Evidence, Derivation


class Graph:
    """In-memory constraint graph. Nodes, edges, observations, evidence, derivations."""
    
    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self.observations: dict[str, Observation] = {}
        self.evidence: dict[str, Evidence] = {}
        self.derivations: dict[str, Derivation] = []
    
    def add(self, obj):
        """Add any POW object to the graph."""
        if isinstance(obj, Node):
            self.nodes[obj.id] = obj
        elif isinstance(obj, Edge):
            self.edges[obj.id] = obj
        elif isinstance(obj, Observation):
            self.observations[obj.id] = obj
        elif isinstance(obj, Evidence):
            self.evidence[obj.id] = obj
        elif isinstance(obj, Derivation):
            self.derivations.append(obj)
    
    def remove(self, obj):
        """Remove any POW object from the graph."""
        if isinstance(obj, Node):
            self.nodes.pop(obj.id, None)
        elif isinstance(obj, Edge):
            self.edges.pop(obj.id, None)
        elif isinstance(obj, Observation):
            self.observations.pop(obj.id, None)
        elif isinstance(obj, Evidence):
            self.evidence.pop(obj.id, None)
    
    def node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)
    
    def edge(self, edge_id: str) -> Optional[Edge]:
        return self.edges.get(edge_id)
    
    def requires(self, node_id: str) -> list[Edge]:
        """What does this node require? (outgoing REQUIRES edges)."""
        return [e for e in self.edges.values() if e.source == node_id and e.relation == "REQUIRES"]
    
    def required_by(self, node_id: str) -> list[Edge]:
        """What requires this node? (incoming REQUIRES edges)."""
        return [e for e in self.edges.values() if e.target == node_id and e.relation == "REQUIRES"]
    
    def upstream(self, node_id: str, max_depth: int = 100) -> list[str]:
        """All nodes that this node depends on, transitively."""
        visited = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for edge in self.requires(current):
                if edge.target not in visited:
                    queue.append(edge.target)
        visited.discard(node_id)
        return list(visited)
    
    def downstream(self, node_id: str, max_depth: int = 100) -> list[str]:
        """All nodes that depend on this node, transitively."""
        visited = set()
        queue = [node_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for edge in self.required_by(current):
                if edge.source not in visited:
                    queue.append(edge.source)
        visited.discard(node_id)
        return list(visited)
    
    def observations_for(self, subject_id: str) -> list[Observation]:
        """All observations about a subject (node or edge)."""
        return [o for o in self.observations.values() if o.subject == subject_id]
    
    def evidence_for(self, target_id: str) -> list[Evidence]:
        """All evidence supporting a target (observation or edge)."""
        return [e for e in self.evidence.values() if e.target == target_id]
    
    def get_observation(self, subject_id: str, metric: str, as_of: str = None) -> Optional[Observation]:
        """Get the latest observation for a subject+metric."""
        candidates = [o for o in self.observations_for(subject_id) if o.metric == metric]
        if as_of:
            candidates = [o for o in candidates if o.as_of <= as_of]
        if not candidates:
            return None
        return max(candidates, key=lambda o: o.as_of)
    
    def load_fixture(self, path: str):
        """Load a JSON fixture file."""
        data = json.loads(Path(path).read_text())
        for item in data.get("nodes", []):
            self.add(Node(**item))
        for item in data.get("edges", []):
            self.add(Edge(**item))
        for item in data.get("observations", []):
            self.add(Observation(**item))
        for item in data.get("evidence", []):
            self.add(Evidence(**item))
    
    def stats(self) -> dict:
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "observations": len(self.observations),
            "evidence": len(self.evidence),
            "derivations": len(self.derivations),
        }
    
    def __repr__(self):
        s = self.stats()
        return f"Graph(nodes={s['nodes']}, edges={s['edges']}, obs={s['observations']}, ev={s['evidence']})"
