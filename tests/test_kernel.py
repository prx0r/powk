"""Tests for POWKernel 0.2."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from pow.canonical import canonical, content_id, make_id
from pow.model import (
    Node, Edge, Observation, Evidence, Derivation,
    make_edge_id, make_obs_id, make_ev_id, make_deriv_id,
)
from pow.graph import Graph
from pow.snapshot import Snapshot
from pow.unknowns import unknowns, unknowns_for_node, summary
from pow.loader import load_json
from pow.store import Store


FIXTURES = Path(__file__).parent.parent / "examples"


# ═══════════════════════════════════════════════════════════
# Canonical
# ═══════════════════════════════════════════════════════════

class TestCanonical:
    def test_deterministic(self):
        a = canonical({"b": 2, "a": 1})
        b = canonical({"a": 1, "b": 2})
        assert a == b

    def test_content_id(self):
        id1 = content_id({"x": 1})
        id2 = content_id({"x": 1})
        assert id1 == id2

    def test_different_inputs_different_ids(self):
        assert content_id({"x": 1}) != content_id({"x": 2})

    def test_make_id_prefix(self):
        assert make_id("node", {"x": 1}).startswith("node:")


# ═══════════════════════════════════════════════════════════
# Model
# ═══════════════════════════════════════════════════════════

class TestModel:
    def test_node_domain_id(self):
        n = Node(id="powuk:capability:5241", kind="capability", label="Electrician")
        assert n.id == "powuk:capability:5241"
        assert not n.id.startswith("node:")

    def test_node_validity(self):
        n = Node(id="x", kind="k", label="l", valid_from="2026-01-01", valid_to="2026-12-31")
        assert n.valid_from == "2026-01-01"
        assert n.valid_to == "2026-12-31"

    def test_edge_structural_only(self):
        e = Edge(id="e1", source="a", target="b", relation="REQUIRES")
        d = e.to_dict()
        assert "capacity" not in d
        assert "utilisation" not in d
        assert "lead_time" not in d

    def test_edge_with_coefficient(self):
        e = Edge(id="e1", source="a", target="b", relation="REQUIRES",
                 coefficient=4.2, coefficient_unit="worker_hours/MW")
        d = e.to_dict()
        assert d["coefficient"] == 4.2
        assert d["coefficient_unit"] == "worker_hours/MW"

    def test_observation_bitemporal(self):
        o = Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="units",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-01-15T00:00:00Z",
            source_dataset="test",
        )
        assert o.effective_at != o.observed_at

    def test_evidence_no_value(self):
        ev = Evidence(id="ev:1", target="obs:1", direction="SUPPORTS", claim="test")
        d = ev.to_dict()
        assert "value" not in d
        assert "unit" not in d

    def test_derivation_model_hash(self):
        d = Derivation(
            id="d:1", kind="test", subject="a", value=1.0, unit="ratio",
            effective_at="2026-01-01", model="m/v1", model_hash="abc123",
        )
        assert d.model_hash == "abc123"


# ═══════════════════════════════════════════════════════════
# Graph
# ═══════════════════════════════════════════════════════════

class TestGraph:
    def test_add_and_query(self):
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Node(id="b", kind="k", label="B"))
        g.add(Edge(id="e1", source="a", target="b", relation="REQUIRES"))
        assert g.node("a").label == "A"
        assert len(g.requires("a")) == 1
        assert len(g.required_by("b")) == 1

    def test_upstream_downstream(self):
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Node(id="b", kind="k", label="B"))
        g.add(Node(id="c", kind="k", label="C"))
        g.add(Edge(id="e1", source="a", target="b", relation="REQUIRES"))
        g.add(Edge(id="e2", source="b", target="c", relation="REQUIRES"))
        assert set(g.upstream("a")) == {"b", "c"}
        assert set(g.downstream("c")) == {"b", "a"}

    def test_roots_and_leaves(self):
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Node(id="b", kind="k", label="B"))
        g.add(Node(id="c", kind="k", label="C"))
        g.add(Edge(id="e1", source="a", target="b", relation="REQUIRES"))
        g.add(Edge(id="e2", source="b", target="c", relation="REQUIRES"))
        assert g.roots() == ["a"]
        assert g.leaves() == ["c"]

    def test_paths(self):
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Node(id="b", kind="k", label="B"))
        g.add(Node(id="c", kind="k", label="C"))
        g.add(Edge(id="e1", source="a", target="b", relation="REQUIRES"))
        g.add(Edge(id="e2", source="b", target="c", relation="REQUIRES"))
        paths = g.paths("a", "c")
        assert len(paths) == 1
        assert paths[0] == ["a", "b", "c"]

    def test_stats(self):
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Edge(id="e1", source="a", target="b", relation="REQUIRES"))
        stats = g.stats()
        assert stats["nodes"] == 1
        assert stats["edges"] == 1


# ═══════════════════════════════════════════════════════════
# Snapshot
# ═══════════════════════════════════════════════════════════

class TestSnapshot:
    def test_build_snapshot(self):
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Node(id="b", kind="k", label="B"))
        g.add(Edge(id="e1", source="a", target="b", relation="REQUIRES"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-01-15T00:00:00Z",
            source_dataset="test",
        ))
        snap = g.build_snapshot("2026-06-01T00:00:00Z")
        assert len(snap.nodes) == 2
        assert snap.observation("a", "capacity").value == 100

    def test_snapshot_temporal_filter(self):
        g = Graph()
        g.add(Node(id="a", kind="k", label="A", valid_from="2026-06-01"))
        g.add(Node(id="b", kind="k", label="B"))
        snap_before = g.build_snapshot("2026-01-01T00:00:00Z")
        snap_after = g.build_snapshot("2026-09-01T00:00:00Z")
        assert "a" not in snap_before.nodes
        assert "a" in snap_after.nodes

    def test_snapshot_latest_observation(self):
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-01-01T00:00:00Z",
            source_dataset="test",
        ))
        g.add(Observation(
            id="obs:2", subject="a", metric="capacity", value=200, unit="u",
            effective_at="2026-06-01T00:00:00Z", observed_at="2026-06-01T00:00:00Z",
            source_dataset="test",
        ))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        assert snap.observation("a", "capacity").value == 200

    def test_counterfactual_override(self):
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-01-01T00:00:00Z",
            source_dataset="test",
        ))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        scenario = snap.with_override(subject="a", metric="capacity", value=200)
        assert snap.observation("a", "capacity").value == 100
        assert scenario.observation("a", "capacity").value == 200

    def test_knowledge_mode(self):
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-06-01T00:00:00Z",
            source_dataset="test",
        ))
        # Knowledge-time: observed_at is July, so at June it's not yet known
        snap_k = g.build_snapshot("2026-03-01T00:00:00Z", mode="knowledge")
        snap_w = g.build_snapshot("2026-03-01T00:00:00Z", mode="world")
        assert snap_k.observation("a", "capacity") is None
        assert snap_w.observation("a", "capacity").value == 100


# ═══════════════════════════════════════════════════════════
# Unknowns
# ═══════════════════════════════════════════════════════════

class TestUnknowns:
    def test_report_missing(self):
        g = Graph()
        g.add(Node(id="a", kind="capability", label="A"))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        result = unknowns(snap)
        assert len(result) == 1
        assert "capacity" in result[0]["missing"]

    def test_report_present(self):
        g = Graph()
        g.add(Node(id="a", kind="capability", label="A"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-01-01T00:00:00Z",
            source_dataset="test",
        ))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        result = unknowns(snap)
        assert "capacity" in result[0]["present"]
        assert "utilisation" in result[0]["missing"]

    def test_summary(self):
        g = Graph()
        g.add(Node(id="a", kind="capability", label="A"))
        g.add(Node(id="b", kind="equipment", label="B"))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        s = summary(snap)
        assert s["total_nodes"] == 2
        assert s["nodes_with_gaps"] > 0


# ═══════════════════════════════════════════════════════════
# Loader
# ═══════════════════════════════════════════════════════════

class TestLoader:
    def test_load_uk_grid(self):
        g = load_json(str(FIXTURES / "uk_grid.json"))
        stats = g.stats()
        assert stats["nodes"] == 5
        assert stats["edges"] == 4
        assert stats["observations"] == 5
        assert stats["evidence"] == 2

    def test_load_repair(self):
        g = load_json(str(FIXTURES / "repair.json"))
        assert g.stats()["nodes"] == 4

    def test_load_compute(self):
        g = load_json(str(FIXTURES / "compute.json"))
        assert g.stats()["nodes"] == 4

    def test_load_ai_datacentre(self):
        g = load_json(str(FIXTURES / "ai_datacentre.json"))
        stats = g.stats()
        assert stats["nodes"] == 5
        assert stats["edges"] == 4


# ═══════════════════════════════════════════════════════════
# Store
# ═══════════════════════════════════════════════════════════

class TestStore:
    def test_append_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            n = Node(id="a", kind="k", label="A")
            store.append(n)
            nodes = list(store.load("nodes"))
            assert len(nodes) == 1
            assert nodes[0]["id"] == "a"

    def test_stats(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            store.append(Node(id="a", kind="k", label="A"))
            store.append(Edge(id="e1", source="a", target="b", relation="REQUIRES"))
            stats = store.stats()
            assert stats["nodes"] == 1
            assert stats["edges"] == 1


# ═══════════════════════════════════════════════════════════
# Cross-Domain (the real test)
# ═══════════════════════════════════════════════════════════

class TestCrossDomain:
    def test_uk_grid_snapshot(self):
        g = load_json(str(FIXTURES / "uk_grid.json"))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        assert len(snap.nodes) == 5
        assert len(snap.edges) == 4
        # Should have observations for all 5 nodes
        for nid in snap.nodes:
            obs = snap.observations_for(nid)
            assert len(obs) > 0, f"No observations for {nid}"

    def test_repair_snapshot(self):
        g = load_json(str(FIXTURES / "repair.json"))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        assert len(snap.nodes) == 4

    def test_compute_snapshot(self):
        g = load_json(str(FIXTURES / "compute.json"))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        assert len(snap.nodes) == 4

    def test_ai_datacentre_cross_garden(self):
        g = load_json(str(FIXTURES / "ai_datacentre.json"))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        # Cross-garden: powai -> powuk -> powflow
        assert "powai:inference_demand" in snap.nodes
        assert "powuk:datacentre" in snap.nodes
        assert "powflow:transformer" in snap.nodes
        # Chain: ai -> dc -> grid -> transformer -> copper
        assert len(snap.paths("powai:inference_demand", "powflow:copper")) == 1

    def test_all_fixtures_same_kernel(self):
        """Verify the kernel handles all four domains with zero domain code."""
        for fixture in ("uk_grid.json", "repair.json", "compute.json", "ai_datacentre.json"):
            g = load_json(str(FIXTURES / fixture))
            snap = g.build_snapshot("2026-09-01T00:00:00Z")
            u = unknowns(snap)
            assert isinstance(u, list)

    def test_no_domain_code_in_kernel(self):
        """Kernel source must not contain domain-specific words."""
        kernel_dir = Path(__file__).parent.parent / "pow"
        domain_words = [
            "electrician", "transformer", "capacitor", "gpu", "semiconductor",
            "inverter", "mosfet", "fab", "hbm", "copper", "steel",
        ]
        for py_file in kernel_dir.glob("*.py"):
            content = py_file.read_text().lower()
            for word in domain_words:
                assert word not in content, f"Domain word '{word}' found in {py_file.name}"
