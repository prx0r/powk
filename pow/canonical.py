"""Canonical serialization and content-addressed IDs.

IDs are content-addressed for immutable RECORDS (observations, evidence, derivations).
NODEs use stable domain-supplied IDs (not content-addressed).
"""

import hashlib
import json


def canonical(obj) -> str:
    """Deterministic JSON serialization."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def content_id(obj) -> str:
    """SHA-256 of canonical form, truncated to 16 hex chars."""
    return hashlib.sha256(canonical(obj).encode()).hexdigest()[:16]


def make_id(prefix: str, obj) -> str:
    """Content-addressed ID with prefix."""
    return f"{prefix}:{content_id(obj)}"
