"""Content-addressed IDs and canonical forms.

Same inputs → same ID. Always.
"""
import hashlib
import json


def canonical(obj):
    """Canonical JSON serialization. Keys sorted, no whitespace, no trailing commas."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def content_id(obj):
    """SHA-256 of canonical form, first 16 hex chars."""
    return hashlib.sha256(canonical(obj).encode()).hexdigest()[:16]


def make_id(prefix, obj):
    """Prefix:content_id. E.g. node:a1b2c3d4e5f6g7h8."""
    return f"{prefix}:{content_id(obj)}"
