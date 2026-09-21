"""Historical snapshot — the centerpiece of POWKernel.

A Snapshot is an immutable reconstruction of the dependency graph
at a specific point in time, with the latest admissible observations.

Two modes:
  world_time    — what was actually true/effective at date t
  knowledge_time — what information was available by date t
"""

from dataclasses import dataclass, field
from typing import Optional

from .model import Node, Edge, Observation, Evidence


@dataclass(frozen=True)
class Snapshot:
    """An immutable graph state at a point in time.

    Contains the nodes, edges, observations, and evidence that were
    valid/available at the specified time.
    """
    at: str                   # ISO timestamp — the snapshot time
    mode: str = "world"       # "world" or "knowledge"
    nodes: dict = field(default_factory=dict)      # node_id -> Node
    edges: dict = field(default_factory=dict)      # edge_id -> Edge
    observations: dict = field(default_factory=dict)  # (subject, metric) -> Observation
    evidence: dict = field(default_factory=dict)   # evidence_id -> Evidence

    def node(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def edge(self, edge_id: str) -> Optional[Edge]:
        return self.edges.get(edge_id)

    def observation(self, subject: str, metric: str) -> Optional[Observation]:
        return self.observations.get((subject, metric))

    def observations_for(self, subject: str) -> list:
        return [obs for (s, m), obs in self.observations.items() if s == subject]

    def edges_from(self, node_id: str) -> list:
        """Outgoing REQUIRES edges from this node."""
        return [e for e in self.edges.values() if e.source == node_id]

    def edges_to(self, node_id: str) -> list:
        """Incoming REQUIRES edges to this node."""
        return [e for e in self.edges.values() if e.target == node_id]

    def upstream(self, node_id: str, max_depth: int = 100) -> list:
        """BFS following outgoing REQUIRES edges (what does this depend on?)."""
        visited = set()
        queue = [node_id]
        depth = 0
        while queue and depth < max_depth:
            next_queue = []
            for nid in queue:
                if nid in visited:
                    continue
                visited.add(nid)
                for edge in self.edges_from(nid):
                    next_queue.append(edge.target)
            queue = next_queue
            depth += 1
        visited.discard(node_id)
        return list(visited)

    def downstream(self, node_id: str, max_depth: int = 100) -> list:
        """BFS following incoming REQUIRES edges (what depends on this?)."""
        visited = set()
        queue = [node_id]
        depth = 0
        while queue and depth < max_depth:
            next_queue = []
            for nid in queue:
                if nid in visited:
                    continue
                visited.add(nid)
                for edge in self.edges_to(nid):
                    next_queue.append(edge.source)
            queue = next_queue
            depth += 1
        visited.discard(node_id)
        return list(visited)

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
        for edge in self.edges_from(current):
            self._dfs_paths(edge.target, target, path, visited, results, depth - 1)
        visited.discard(current)

    def roots(self) -> list:
        """Nodes with no incoming edges (top-level dependents)."""
        targets = {e.target for e in self.edges.values()}
        return [nid for nid in self.nodes if nid not in targets]

    def leaves(self) -> list:
        """Nodes with no outgoing edges (base resources)."""
        sources = {e.source for e in self.edges.values()}
        return [nid for nid in self.nodes if nid not in sources]

    def to_dict(self) -> dict:
        return {
            "at": self.at,
            "mode": self.mode,
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges.values()],
            "observations": [o.to_dict() for o in self.observations.values()],
            "evidence": [ev.to_dict() for ev in self.evidence.values()],
        }

    def with_override(self, subject: str, metric: str, value: float,
                      unit: str = None, source_dataset: str = "counterfactual") -> "Snapshot":
        """Create a new snapshot with an overridden observation.

        This is the counterfactual primitive. It creates a NEW immutable
        snapshot — the original is never mutated.
        """
        from .model import make_obs_id
        new_obs = Observation(
            id=make_obs_id(subject, metric, value, unit, self.at, self.at, source_dataset),
            subject=subject,
            metric=metric,
            value=value,
            unit=unit,
            effective_at=self.at,
            observed_at=self.at,
            source_dataset=source_dataset,
        )
        new_obs_dict = dict(self.observations)
        new_obs_dict[(subject, metric)] = new_obs
        return Snapshot(
            at=self.at,
            mode=self.mode,
            nodes=dict(self.nodes),
            edges=dict(self.edges),
            observations=new_obs_dict,
            evidence=dict(self.evidence),
        )
