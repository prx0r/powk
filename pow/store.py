"""Store — append-only JSONL persistence.

Each object type gets its own directory. Objects are stored as
JSON lines, one per file keyed by content-addressed ID.
"""

import json
import os
from pathlib import Path
from typing import Iterator


class Store:
    """Append-only JSONL store for POWKernel objects."""

    def __init__(self, root: str = "store"):
        self.root = Path(root)
        for cat in ("nodes", "edges", "observations", "evidence", "derivations"):
            (self.root / cat).mkdir(parents=True, exist_ok=True)

    def _path(self, category: str, obj_id: str) -> Path:
        return self.root / category / f"{obj_id}.jsonl"

    def append(self, obj) -> str:
        """Append an object to its category file."""
        from .model import Node, Edge, Observation, Evidence, Derivation
        d = obj.to_dict()
        if isinstance(obj, Node):
            cat = "nodes"
        elif isinstance(obj, Edge):
            cat = "edges"
        elif isinstance(obj, Observation):
            cat = "observations"
        elif isinstance(obj, Evidence):
            cat = "evidence"
        elif isinstance(obj, Derivation):
            cat = "derivations"
        else:
            raise ValueError(f"Unknown type: {type(obj)}")

        path = self._path(cat, obj.id)
        with open(path, "a") as f:
            f.write(json.dumps(d, default=str) + "\n")
        return str(path)

    def append_many(self, objects) -> list:
        return [self.append(o) for o in objects]

    def load(self, category: str) -> Iterator[dict]:
        """Load all entries from a category."""
        cat_dir = self.root / category
        if not cat_dir.exists():
            return
        for p in sorted(cat_dir.glob("*.jsonl")):
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        yield json.loads(line)

    def load_all(self) -> dict:
        return {cat: list(self.load(cat))
                for cat in ("nodes", "edges", "observations", "evidence", "derivations")}

    def stats(self) -> dict:
        return {
            cat: len(list((self.root / cat).glob("*.jsonl")))
            for cat in ("nodes", "edges", "observations", "evidence", "derivations")
        }
