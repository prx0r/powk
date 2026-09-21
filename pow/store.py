"""Append-only JSONL store.

One line per object. Content-addressed filenames.
Never rewrite. Never overwrite.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Iterator
from .model import Node, Edge, Observation, Evidence, Derivation


class Store:
    """Append-only JSONL store for POW objects."""
    
    def __init__(self, root: str = "store"):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        for subdir in ["nodes", "edges", "observations", "evidence", "derivations"]:
            (self.root / subdir).mkdir(exist_ok=True)
    
    def _path(self, category: str, obj_id: str) -> Path:
        return self.root / category / f"{obj_id}.jsonl"
    
    def append(self, obj) -> str:
        """Append an object to the store. Returns the file path."""
        if isinstance(obj, Node):
            path = self._path("nodes", obj.id)
            data = obj.to_dict()
        elif isinstance(obj, Edge):
            path = self._path("edges", obj.id)
            data = obj.to_dict()
        elif isinstance(obj, Observation):
            path = self._path("observations", obj.id)
            data = obj.to_dict()
        elif isinstance(obj, Evidence):
            path = self._path("evidence", obj.id)
            data = obj.to_dict()
        elif isinstance(obj, Derivation):
            path = self._path("derivations", obj.id)
            data = obj.to_dict()
        else:
            raise ValueError(f"Unknown object type: {type(obj)}")
        
        with open(path, "a") as f:
            f.write(json.dumps(data, default=str) + "\n")
        
        return str(path)
    
    def append_many(self, objects) -> list[str]:
        """Append multiple objects."""
        return [self.append(obj) for obj in objects]
    
    def load(self, category: str) -> Iterator[dict]:
        """Load all objects from a category."""
        dir_path = self.root / category
        if not dir_path.exists():
            return
        for path in sorted(dir_path.glob("*.jsonl")):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)
    
    def load_all(self) -> dict[str, list[dict]]:
        """Load all objects from the store."""
        result = {}
        for cat in ["nodes", "edges", "observations", "evidence", "derivations"]:
            result[cat] = list(self.load(cat))
        return result
    
    def stats(self) -> dict:
        stats = {}
        for cat in ["nodes", "edges", "observations", "evidence", "derivations"]:
            dir_path = self.root / cat
            if dir_path.exists():
                stats[cat] = len(list(dir_path.glob("*.jsonl")))
            else:
                stats[cat] = 0
        return stats
