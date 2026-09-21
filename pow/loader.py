"""Loader — import graphs from JSONL and JSON fixtures."""

import json
from pathlib import Path

from .graph import Graph
from .model import Node, Edge, Observation, Evidence


def load_json(path: str) -> Graph:
    """Load a JSON fixture into a Graph."""
    g = Graph()
    g.load_fixture(path)
    return g


def load_jsonl(path: str) -> Graph:
    """Load a JSONL file (one record per line) into a Graph."""
    g = Graph()
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            kind = obj.get("kind", obj.get("type", ""))
            if kind == "node" or "kind" in obj and "label" in obj and "id" in obj and not obj.get("source"):
                g.add(Node(
                    id=obj["id"], kind=obj.get("kind", ""),
                    label=obj.get("label", ""),
                    valid_from=obj.get("valid_from"),
                    valid_to=obj.get("valid_to"),
                ))
            elif kind == "edge" or "source" in obj and "target" in obj and "relation" in obj:
                g.add(Edge(
                    id=obj["id"], source=obj["source"], target=obj["target"],
                    relation=obj["relation"],
                    coefficient=obj.get("coefficient"),
                    coefficient_unit=obj.get("coefficient_unit"),
                    valid_from=obj.get("valid_from"),
                    valid_to=obj.get("valid_to"),
                ))
            elif kind == "observation" or "metric" in obj and "subject" in obj:
                g.add(Observation(
                    id=obj["id"], subject=obj["subject"], metric=obj["metric"],
                    value=obj.get("value"), unit=obj.get("unit"),
                    effective_at=obj.get("effective_at", obj.get("as_of", "")),
                    observed_at=obj.get("observed_at", obj.get("effective_at", "")),
                    source_dataset=obj.get("source_dataset", obj.get("source", "")),
                ))
            elif kind == "evidence" or "claim" in obj and "target" in obj:
                g.add(Evidence(
                    id=obj["id"], target=obj["target"],
                    direction=obj.get("direction", "SUPPORTS"),
                    claim=obj.get("claim", ""),
                    source_uri=obj.get("source_uri"),
                    publisher=obj.get("publisher"),
                    published_at=obj.get("published_at"),
                    retrieved_at=obj.get("retrieved_at"),
                    lineage_root=obj.get("lineage_root"),
                    content_hash=obj.get("content_hash"),
                ))
    return g


def load_directory(path: str) -> Graph:
    """Load all JSON/JSONL files from a directory into a single Graph."""
    g = Graph()
    p = Path(path)
    for f in sorted(p.glob("*.json")):
        g.load_fixture(str(f))
    for f in sorted(p.glob("*.jsonl")):
        child = load_jsonl(str(f))
        for node in child.nodes.values():
            g.add(node)
        for edge in child.edges.values():
            g.add(edge)
        for obs in child.observations:
            g.add(obs)
        for ev in child.evidence.values():
            g.add(ev)
    return g
