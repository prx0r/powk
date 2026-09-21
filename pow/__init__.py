"""POWKernel — deterministic Layer-2 substrate for dependency constraint analysis.

Five canonical types:
    Node, Edge, Observation, Evidence, Derivation

Core primitive:
    build_snapshot(at, mode) — reconstruct graph state at time t
"""

from .model import (
    Node, Edge, Observation, Evidence, Derivation,
    make_edge_id, make_obs_id, make_ev_id, make_deriv_id,
)
from .canonical import canonical, content_id, make_id
from .graph import Graph
from .snapshot import Snapshot
from .unknowns import unknowns, unknowns_for_node, summary as unknowns_summary
from .loader import load_json, load_jsonl, load_directory
from .store import Store
from .model_base import Model

__version__ = "0.2.0"
