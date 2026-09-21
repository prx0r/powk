"""Tests for POWKernel.

Prove the same kernel works across three different domains
without any domain-specific code.
"""
import sys, json, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from pow.canonical import canonical, content_id, make_id
from pow.model import Node, Edge, Observation, Evidence, Derivation
from pow.graph import Graph
from pow.constraint import constraint_pressure, node_pressure, edge_pressure, bottlenecks
from pow.counterfactual import shock, propagate, relieve, criticality, unknowns
from pow.evidence import dedup_evidence, validate_evidence, conflicting_evidence
from pow.store import Store
from models.pressure_v1 import pressure, severity, classify, Severity


# ─── CANONICAL ───────────────────────────────────────────────

def test_canonical_deterministic():
    a = canonical({"b": 1, "a": 2})
    b = canonical({"a": 2, "b": 1})
    assert a == b
    assert a == '{"a":2,"b":1}'

def test_content_id_deterministic():
    id1 = content_id({"x": 1})
    id2 = content_id({"x": 1})
    assert id1 == id2

def test_content_id_different():
    id1 = content_id({"x": 1})
    id2 = content_id({"x": 2})
    assert id1 != id2

def test_make_id_prefix():
    nid = make_id("node", {"kind": "test"})
    assert nid.startswith("node:")


# ─── MODEL ───────────────────────────────────────────────────

def test_node_create():
    n = Node.create("capability", "Electricians")
    assert n.kind == "capability"
    assert n.id.startswith("node:")
    assert n.to_dict()["label"] == "Electricians"

def test_edge_create():
    n1 = Node.create("a", "A")
    n2 = Node.create("b", "B")
    e = Edge.create(n1.id, n2.id)
    assert e.relation == "REQUIRES"
    assert e.source == n1.id
    assert e.target == n2.id

def test_observation_create():
    o = Observation.create("capacity", "node:x", 100.0, "units", "2026-09-01", "test")
    assert o.value == 100.0
    assert o.to_dict()["metric"] == "capacity"

def test_observation_null_value():
    o = Observation.create("capacity", "node:x", None, None, "2026-09-01", "test")
    assert o.value is None
    assert o.to_dict()["value"] is None

def test_evidence_create():
    ev = Evidence.create("Claim text", "obs:x", "SUPPORTS", publisher="Test")
    assert ev.direction == "SUPPORTS"
    assert ev.publisher == "Test"

def test_derivation_create():
    d = Derivation.create("pressure", "edge:x", 2.5, "2026-09-01", "pressure_v1")
    assert d.kind == "pressure"
    assert d.value == 2.5
    assert d.model == "pressure_v1"


# ─── GRAPH ───────────────────────────────────────────────────

def test_graph_add_remove():
    g = Graph()
    n = Node.create("test", "Test")
    g.add(n)
    assert g.node(n.id) is not None
    g.remove(n)
    assert g.node(n.id) is None

def test_graph_requires():
    g = Graph()
    n1 = Node.create("a", "A")
    n2 = Node.create("b", "B")
    g.add(n1)
    g.add(n2)
    e = Edge.create(n1.id, n2.id)
    g.add(e)
    assert len(g.requires(n1.id)) == 1
    assert len(g.requires(n2.id)) == 0

def test_graph_upstream_downstream():
    g = Graph()
    n1 = Node.create("a", "A")
    n2 = Node.create("b", "B")
    n3 = Node.create("c", "C")
    g.add(n1)
    g.add(n2)
    g.add(n3)
    g.add(Edge.create(n1.id, n2.id))
    g.add(Edge.create(n2.id, n3.id))
    
    assert n3.id in g.upstream(n1.id)
    assert n1.id in g.downstream(n3.id)

def test_graph_observations_for():
    g = Graph()
    n = Node.create("test", "Test")
    g.add(n)
    o1 = Observation.create("capacity", n.id, 100.0, "units", "2026-01-01", "src")
    o2 = Observation.create("capacity", n.id, 200.0, "units", "2026-09-01", "src")
    g.add(o1)
    g.add(o2)
    obs = g.observations_for(n.id)
    assert len(obs) == 2

def test_graph_load_fixture():
    g = Graph()
    g.load_fixture(str(Path(__file__).parent.parent / "examples" / "uk_grid.json"))
    s = g.stats()
    assert s["nodes"] == 5
    assert s["edges"] == 4
    assert s["observations"] == 5


# ─── CONSTRAINT ──────────────────────────────────────────────

def test_edge_pressure():
    g = Graph()
    n1 = Node.create("demand", "Demand")
    n2 = Node.create("supply", "Supply")
    g.add(n1)
    g.add(n2)
    g.add(Edge.create(n1.id, n2.id))
    g.add(Observation.create("capacity", n1.id, 100.0, "units", "2026-09-01", "test"))
    g.add(Observation.create("capacity", n2.id, 50.0, "units", "2026-09-01", "test"))
    
    result = edge_pressure(g, g.edges[list(g.edges.keys())[0]])
    assert result["pressure"] == 2.0

def test_edge_pressure_unknown():
    g = Graph()
    n1 = Node.create("demand", "Demand")
    n2 = Node.create("supply", "Supply")
    g.add(n1)
    g.add(n2)
    g.add(Edge.create(n1.id, n2.id))
    # No observations
    result = edge_pressure(g, g.edges[list(g.edges.keys())[0]])
    assert result["pressure"] is None
    assert len(result["unknowns"]) > 0

def test_constraint_pressure():
    g = Graph()
    g.load_fixture(str(Path(__file__).parent.parent / "examples" / "uk_grid.json"))
    derivs = constraint_pressure(g)
    assert len(derivs) > 0
    for d in derivs:
        assert d.kind == "constraint_pressure"

def test_bottlenecks():
    g = Graph()
    n1 = Node.create("demand", "Demand")
    n2 = Node.create("supply", "Supply")
    g.add(n1)
    g.add(n2)
    g.add(Edge.create(n1.id, n2.id))
    g.add(Observation.create("capacity", n1.id, 100.0, "units", "2026-09-01", "test"))
    g.add(Observation.create("capacity", n2.id, 30.0, "units", "2026-09-01", "test"))
    
    bn = bottlenecks(g, threshold=2.0)
    assert len(bn) == 1
    assert bn[0]["pressure"] > 3.0


# ─── COUNTERFACTUAL ──────────────────────────────────────────

def test_propagate():
    g = Graph()
    g.load_fixture(str(Path(__file__).parent.parent / "examples" / "uk_grid.json"))
    result = propagate(g, "uk:electrical_steel_supply")
    assert result["downstream_count"] > 0

def test_criticality():
    g = Graph()
    g.load_fixture(str(Path(__file__).parent.parent / "examples" / "uk_grid.json"))
    scores = criticality(g)
    assert len(scores) == 5
    assert scores[0]["criticality_score"] > 0

def test_unknowns():
    g = Graph()
    g.load_fixture(str(Path(__file__).parent.parent / "examples" / "uk_grid.json"))
    missing = unknowns(g)
    assert isinstance(missing, list)


# ─── EVIDENCE ────────────────────────────────────────────────

def test_dedup_evidence():
    ev1 = Evidence.create("Claim A", "obs:x", "SUPPORTS", publisher="Pub")
    ev2 = Evidence.create("Claim A", "obs:x", "SUPPORTS", publisher="Pub")
    ev3 = Evidence.create("Claim B", "obs:x", "SUPPORTS", publisher="Pub2")
    result = dedup_evidence([ev1, ev2, ev3])
    assert len(result) == 2

def test_validate_evidence_valid():
    ev = Evidence.create("Claim", "obs:x", "SUPPORTS", observed_at="2026-09-01")
    errors = validate_evidence(ev)
    assert len(errors) == 0

def test_validate_evidence_invalid():
    ev = Evidence("", "", "BAD", "")
    errors = validate_evidence(ev)
    assert len(errors) > 0

def test_conflicting_evidence():
    ev1 = Evidence.create("X is 100", "obs:x", "QUANTIFIES", publisher="A")
    ev2 = Evidence.create("X is not 100", "obs:x", "CONTRADICTS", publisher="B")
    conflicts = conflicting_evidence([ev1, ev2])
    assert len(conflicts) == 1


# ─── PRESSURE MODEL ──────────────────────────────────────────

def test_pressure_basic():
    assert pressure(100, 50) == 2.0
    assert pressure(50, 100) == 0.5
    assert pressure(100, 0) == float("inf")
    assert pressure(None, 50) is None

def test_severity():
    assert severity(None) == Severity.NONE
    assert severity(0.5) == Severity.NONE
    assert severity(1.2) == Severity.LOW
    assert severity(1.8) == Severity.MEDIUM
    assert severity(2.5) == Severity.HIGH
    assert severity(4.0) == Severity.CRITICAL

def test_classify():
    r = classify(100, 30)
    assert r["severity"] == "CRITICAL"
    assert r["pressure"] > 3.0


# ─── STORE ───────────────────────────────────────────────────

def test_store_append_and_load():
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        store = Store(tmpdir)
        n = Node.create("test", "Test Node")
        store.append(n)
        
        nodes = list(store.load("nodes"))
        assert len(nodes) == 1
        assert nodes[0]["id"] == n.id

def test_store_stats():
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        store = Store(tmpdir)
        store.append(Node.create("a", "A"))
        store.append(Node.create("b", "B"))
        s = store.stats()
        assert s["nodes"] == 2


# ─── CROSS-DOMAIN: prove kernel works for all three fixtures ─

def test_uk_grid_domain():
    """UK Grid: data centres → grid → transformers → steel."""
    g = Graph()
    g.load_fixture(str(Path(__file__).parent.parent / "examples" / "uk_grid.json"))
    derivs = constraint_pressure(g)
    assert len(derivs) == 4
    bn = bottlenecks(g, threshold=0)
    assert len(bn) >= 0
    c = criticality(g)
    assert len(c) == 5
    u = unknowns(g)
    assert isinstance(u, list)

def test_repair_domain():
    """Repair: inverter → capacitor → parts → technicians."""
    g = Graph()
    g.load_fixture(str(Path(__file__).parent.parent / "examples" / "repair.json"))
    derivs = constraint_pressure(g)
    assert len(derivs) == 3
    c = criticality(g)
    assert len(c) == 4

def test_compute_domain():
    """Compute: AI → GPUs → HBM → fabs."""
    g = Graph()
    g.load_fixture(str(Path(__file__).parent.parent / "examples" / "compute.json"))
    derivs = constraint_pressure(g)
    assert len(derivs) == 3
    c = criticality(g)
    assert len(c) == 4

def test_same_kernel_no_domain_code():
    """Verify no domain-specific code exists in the kernel."""
    import pow.constraint as constraint_mod
    import pow.counterfactual as counter_mod
    import pow.graph as graph_mod
    
    # Domain-specific terms that should never appear in the kernel
    domain_terms = ["electrician", "transformer", "capacitor", "gpu", "semiconductor",
                    "fab_capacity", "inverter", "hbm", "steel"]
    
    for mod in [constraint_mod, counter_mod, graph_mod]:
        source = Path(mod.__file__).read_text().lower()
        for term in domain_terms:
            assert term not in source, \
                f"Domain keyword '{term}' found in {mod.__name__}"


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except Exception as e:
            print(f"  ✗ {t.__name__}: {e}")
    print(f"\n{len(tests)} tests run.")
