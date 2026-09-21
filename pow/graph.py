"""Graph — in-memory container and snapshot builder.

The graph stores the full append-only history. The Snapshot is a
time-travelled view of the graph at a specific point in time.
"""

from typing import Optional
from datetime import datetime, timezone

from .model import Node, Edge, Observation, Evidence, Derivation
from .snapshot import Snapshot


class Graph:
    """Append-only dependency graph with temporal snapshot support."""

    def __init__(self):
        self.nodes: dict[str, Node] = {}
        self.edges: dict[str, Edge] = {}
        self.observations: list[Observation] = []
        self.evidence: dict[str, Evidence] = {}
        self.derivations: list[Derivation] = []

    def add(self, obj) -> None:
        if isinstance(obj, Node):
            self.nodes[obj.id] = obj
        elif isinstance(obj, Edge):
            self.edges[obj.id] = obj
        elif isinstance(obj, Observation):
            self.observations.append(obj)
        elif isinstance(obj, Evidence):
            self.evidence[obj.id] = obj
        elif isinstance(obj, Derivation):
            self.derivations.append(obj)

    def remove(self, obj) -> None:
        if isinstance(obj, Node):
            self.nodes.pop(obj.id, None)
        elif isinstance(obj, Edge):
            self.edges.pop(obj.id, None)
        elif isinstance(obj, Evidence):
            self.evidence.pop(obj.id, None)

    def node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def edge(self, edge_id: str) -> Optional[Edge]:
        return self.edges.get(edge_id)

    def requires(self, node_id: str) -> list:
        """Outgoing REQUIRES edges from this node."""
        return [e for e in self.edges.values()
                if e.source == node_id and e.relation == "REQUIRES"]

    def required_by(self, node_id: str) -> list:
        """Incoming REQUIRES edges to this node."""
        return [e for e in self.edges.values()
                if e.target == node_id and e.relation == "REQUIRES"]

    def upstream(self, node_id: str, max_depth: int = 100) -> list:
        """BFS following outgoing REQUIRES edges."""
        visited = set()
        queue = [node_id]
        depth = 0
        while queue and depth < max_depth:
            next_queue = []
            for nid in queue:
                if nid in visited:
                    continue
                visited.add(nid)
                for edge in self.requires(nid):
                    next_queue.append(edge.target)
            queue = next_queue
            depth += 1
        visited.discard(node_id)
        return list(visited)

    def downstream(self, node_id: str, max_depth: int = 100) -> list:
        """BFS following incoming REQUIRES edges."""
        visited = set()
        queue = [node_id]
        depth = 0
        while queue and depth < max_depth:
            next_queue = []
            for nid in queue:
                if nid in visited:
                    continue
                visited.add(nid)
                for edge in self.required_by(nid):
                    next_queue.append(edge.source)
            queue = next_queue
            depth += 1
        visited.discard(node_id)
        return list(visited)

    def roots(self) -> list:
        """Nodes with no incoming edges (top-level dependents)."""
        targets = {e.target for e in self.edges.values()}
        return [nid for nid in self.nodes if nid not in targets]

    def leaves(self) -> list:
        """Nodes with no outgoing edges (base resources)."""
        sources = {e.source for e in self.edges.values()}
        return [nid for nid in self.nodes if nid not in sources]

    def paths(self, source: str, target: str, max_depth: int = 10) -> list:
        """Find all paths from source to target following REQUIRES edges."""
        results = []
        self._dfs_paths(source, target, [], set(), results, max_depth)
        return results

    def _dfs_paths(self, current, target, path, visited, results, depth):
        if depth <= 0:
            return
        if current in visited:
            return
        path = path + [current]
        if current == target:
            results.append(path)
            return
        visited.add(current)
        for edge in self.requires(current):
            self._dfs_paths(edge.target, target, path, visited, results, depth - 1)
        visited.discard(current)

    def observations_for(self, subject_id: str) -> list:
        return [o for o in self.observations if o.subject == subject_id]

    def evidence_for(self, target_id: str) -> list:
        return [ev for ev in self.evidence.values() if ev.target == target_id]

    def get_observation(self, subject_id: str, metric: str,
                        before: str = None) -> Optional[Observation]:
        """Get the latest observation for a subject+metric, optionally before a timestamp."""
        candidates = [
            o for o in self.observations
            if o.subject == subject_id and o.metric == metric
        ]
        if before:
            candidates = [o for o in candidates if o.effective_at <= before]
        if not candidates:
            return None
        return max(candidates, key=lambda o: o.effective_at)

    def build_snapshot(self, at: str, mode: str = "world") -> Snapshot:
        """Build a dated snapshot of the graph.

        For mode="world": includes nodes/edges valid at time `at`,
        and the latest observation with effective_at <= at.
        For mode="knowledge": includes only observations with observed_at <= at.
        """
        # Filter nodes valid at time at
        nodes = {}
        for nid, node in self.nodes.items():
            if node.valid_from and node.valid_from > at:
                continue
            if node.valid_to and node.valid_to <= at:
                continue
            nodes[nid] = node

        # Filter edges valid at time at
        edges = {}
        for eid, edge in self.edges.items():
            if edge.valid_from and edge.valid_from > at:
                continue
            if edge.valid_to and edge.valid_to <= at:
                continue
            # Both endpoints must exist
            if edge.source not in nodes or edge.target not in nodes:
                continue
            edges[eid] = edge

        # Get latest admissible observations
        obs_map = {}  # (subject, metric) -> latest Observation
        for o in self.observations:
            if o.subject not in nodes and o.subject not in edges:
                continue
            if mode == "knowledge" and o.observed_at > at:
                continue
            if o.effective_at > at:
                continue
            key = (o.subject, o.metric)
            if key not in obs_map or o.effective_at > obs_map[key].effective_at:
                obs_map[key] = o

        # Evidence attached to surviving observations and edges
        surviving_obs_ids = {o.id for o in obs_map.values()}
        surviving_edge_ids = set(edges.keys())
        ev_map = {}
        for evid, ev in self.evidence.items():
            if ev.target in surviving_obs_ids or ev.target in surviving_edge_ids:
                ev_map[evid] = ev

        return Snapshot(
            at=at,
            mode=mode,
            nodes=nodes,
            edges=edges,
            observations=obs_map,
            evidence=ev_map,
        )

    def load_fixture(self, path: str) -> None:
        """Load a JSON fixture with nodes, edges, observations, evidence."""
        import json
        with open(path) as f:
            data = json.load(f)
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
