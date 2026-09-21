"""Store — content-addressed, write-once persistence.

Each object is stored as one immutable JSON file keyed by its ID.
Writing the same bytes twice is a no-op.
Writing different bytes to the same ID raises ConflictError.
"""

import json
import os
from pathlib import Path
from typing import Iterator


class ConflictError(Exception):
    """Raised when attempting to write different bytes to an existing record ID."""
    pass


class Store:
    """Content-addressed, write-once JSON store for POWKernel objects."""

    def __init__(self, root: str = "store"):
        self.root = Path(root)
        for cat in ("nodes", "edges", "observations", "evidence", "derivations"):
            (self.root / cat).mkdir(parents=True, exist_ok=True)

    def _path(self, category: str, obj_id: str) -> Path:
        return self.root / category / f"{obj_id}.json"

    def append(self, obj) -> str:
        """Write an object once. Idempotent for identical bytes, raises on collision."""
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
        new_bytes = json.dumps(d, sort_keys=True, default=str).encode()

        if path.exists():
            existing = path.read_bytes()
            if existing == new_bytes:
                return str(path)  # idempotent no-op
            raise ConflictError(
                f"ID collision: {obj.id} exists with different bytes"
            )

        # Atomic write: write to tmp, then rename
        tmp = path.with_suffix(".tmp")
        with open(tmp, "wb") as f:
            f.write(new_bytes)
        os.replace(tmp, path)
        return str(path)

    def append_many(self, objects) -> list:
        return [self.append(o) for o in objects]

    def load(self, category: str) -> Iterator[dict]:
        """Load all entries from a category."""
        cat_dir = self.root / category
        if not cat_dir.exists():
            return
        for p in sorted(cat_dir.glob("*.json")):
            with open(p) as f:
                yield json.load(f)

    def load_all(self) -> dict:
        return {cat: list(self.load(cat))
                for cat in ("nodes", "edges", "observations", "evidence", "derivations")}

    def stats(self) -> dict:
        return {
            cat: len(list((self.root / cat).glob("*.json")))
            for cat in ("nodes", "edges", "observations", "evidence", "derivations")
        }
