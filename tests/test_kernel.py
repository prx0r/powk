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
from pow.graph import Graph, ConflictError
from pow.snapshot import Snapshot
from pow.unknowns import unknowns, unknowns_for_node, summary
from pow.loader import load_json
from pow.store import Store
from pow.store import ConflictError as StoreConflictError
from pow.model_base import hash_file


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

    def test_edge_no_coefficients(self):
        e = Edge(id="e1", source="a", target="b", relation="REQUIRES")
        d = e.to_dict()
        assert "coefficient" not in d
        assert "coefficient_unit" not in d

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
    def test_report_null_metrics(self):
        """Unknowns reports metrics with null values."""
        g = Graph()
        g.add(Node(id="a", kind="capability", label="A"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=None, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-01-01T00:00:00Z",
            source_dataset="test",
        ))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        result = unknowns(snap)
        assert len(result) == 1
        assert "capacity" in result[0]["missing"]

    def test_report_present(self):
        """Unknowns reports non-null metrics as present."""
        g = Graph()
        g.add(Node(id="a", kind="capability", label="A"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-01-01T00:00:00Z",
            source_dataset="test",
        ))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        result = unknowns(snap)
        assert len(result) == 1
        assert "capacity" in result[0]["present"]
        assert result[0]["missing"] == []

    def test_with_requirements(self):
        """Unknowns with model requirements checks specific metrics."""
        g = Graph()
        g.add(Node(id="a", kind="capability", label="A"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-01-01T00:00:00Z",
            source_dataset="test",
        ))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        requirements = [{"subject_kind": "capability", "metric": "capacity"},
                        {"subject_kind": "capability", "metric": "utilisation"}]
        result = unknowns(snap, requirements)
        assert "capacity" in result[0]["present"]
        assert "utilisation" in result[0]["missing"]

    def test_summary(self):
        g = Graph()
        g.add(Node(id="a", kind="capability", label="A"))
        g.add(Node(id="b", kind="equipment", label="B"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=None, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-01-01T00:00:00Z",
            source_dataset="test",
        ))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        s = summary(snap)
        assert s["total_nodes"] == 2
        assert s["nodes_with_gaps"] == 1


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


# ═══════════════════════════════════════════════════════════
# P0 Invariant Tests
# ═══════════════════════════════════════════════════════════

class TestContentAddressing:
    """P0.2: Record IDs must be content-addressed."""

    def test_obs_same_content_same_id(self):
        """Same content produces same ID from factory."""
        id1 = make_obs_id("a", "m", 100, "u", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test")
        id2 = make_obs_id("a", "m", 100, "u", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test")
        assert id1 == id2

    def test_obs_different_value_different_id(self):
        id1 = make_obs_id("a", "m", 100, "u", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test")
        id2 = make_obs_id("a", "m", 120, "u", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test")
        assert id1 != id2

    def test_obs_different_observed_at_different_id(self):
        id1 = make_obs_id("a", "m", 100, "u", "2026-01-01T00:00:00Z", "2026-02-01T00:00:00Z", "test")
        id2 = make_obs_id("a", "m", 100, "u", "2026-01-01T00:00:00Z", "2026-03-01T00:00:00Z", "test")
        assert id1 != id2

    def test_obs_different_unit_different_id(self):
        id1 = make_obs_id("a", "m", 100, "kg", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test")
        id2 = make_obs_id("a", "m", 100, "lb", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", "test")
        assert id1 != id2

    def test_ev_same_content_same_id(self):
        id1 = make_ev_id("a", "SUPPORTS", "test")
        id2 = make_ev_id("a", "SUPPORTS", "test")
        assert id1 == id2

    def test_ev_different_claim_different_id(self):
        id1 = make_ev_id("a", "SUPPORTS", "foo")
        id2 = make_ev_id("a", "SUPPORTS", "bar")
        assert id1 != id2


class TestIdempotentStore:
    """P0.3: Store must be write-once and idempotent."""

    def test_write_same_bytes_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            n = Node(id="a", kind="k", label="A")
            store.append(n)
            store.append(n)  # idempotent
            nodes = list(store.load("nodes"))
            assert len(nodes) == 1

    def test_write_different_bytes_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(tmp)
            n1 = Node(id="a", kind="k", label="A")
            n2 = Node(id="a", kind="k", label="B")
            store.append(n1)
            with pytest.raises(StoreConflictError):
                store.append(n2)


class TestAppendOnlyGraph:
    """P0.4: Graph must reject mutation."""

    def test_add_same_object_noop(self):
        g = Graph()
        n = Node(id="a", kind="k", label="A")
        g.add(n)
        g.add(n)  # no-op
        assert len(g.nodes) == 1

    def test_add_same_id_different_data_raises(self):
        g = Graph()
        n1 = Node(id="a", kind="k", label="A")
        n2 = Node(id="a", kind="k", label="B")
        g.add(n1)
        with pytest.raises(ConflictError):
            g.add(n2)

    def test_no_remove_method(self):
        g = Graph()
        assert not hasattr(g, 'remove')


class TestKnowledgeTimeAntiLookahead:
    """P0.5/P0.9: Knowledge snapshots must not leak future information."""

    def test_observation_observed_after_snapshot_excluded(self):
        """Observation with observed_at after snapshot time excluded in knowledge mode."""
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-03-01T00:00:00Z",
            source_dataset="test",
        ))
        # Knowledge snapshot in February — observation not yet known
        snap_k = g.build_snapshot("2026-02-01T00:00:00Z", mode="knowledge")
        snap_w = g.build_snapshot("2026-02-01T00:00:00Z", mode="world")
        assert snap_k.observation("a", "capacity") is None
        assert snap_w.observation("a", "capacity").value == 100

    def test_observation_observed_before_snapshot_included(self):
        """Observation with observed_at before snapshot time included in knowledge mode."""
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-01-15T00:00:00Z",
            source_dataset="test",
        ))
        snap = g.build_snapshot("2026-02-01T00:00:00Z", mode="knowledge")
        assert snap.observation("a", "capacity").value == 100

    def test_evidence_retrieved_after_excluded(self):
        """Evidence retrieved after snapshot time excluded in knowledge mode."""
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-01-15T00:00:00Z",
            source_dataset="test",
        ))
        g.add(Evidence(
            id="ev:1", target="obs:1", direction="SUPPORTS", claim="test",
            retrieved_at="2026-03-01T00:00:00Z",
        ))
        # Knowledge snapshot in February — evidence not yet retrieved
        snap_k = g.build_snapshot("2026-02-01T00:00:00Z", mode="knowledge")
        snap_w = g.build_snapshot("2026-02-01T00:00:00Z", mode="world")
        assert len(snap_k.evidence) == 0
        assert len(snap_w.evidence) == 1

    def test_edge_observed_after_excluded(self):
        """Edge observed after snapshot time excluded in knowledge mode.

        NOTE: This test requires Edge.observed_at to be implemented.
        Currently Edge does not have observed_at. This test validates the
        snapshot logic once Edge gains a knowledge timestamp.
        """
        # Edge doesn't have observed_at yet — skip this specific test
        # The snapshot code has hasattr check for forward compatibility
        pass


class TestRevisionHandling:
    """P0.5: Snapshot must select revision deterministically."""

    def test_knowledge_snapshot_selects_latest_known(self):
        """Knowledge snapshot selects latest observation by (effective_at, observed_at, id)."""
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        # Two revisions of same metric, same effective_at
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-02-01T00:00:00Z",
            source_dataset="test",
        ))
        g.add(Observation(
            id="obs:2", subject="a", metric="capacity", value=120, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-03-01T00:00:00Z",
            source_dataset="test",
        ))
        # Knowledge snapshot in February: only obs:1 known
        snap_feb = g.build_snapshot("2026-02-15T00:00:00Z", mode="knowledge")
        assert snap_feb.observation("a", "capacity").value == 100
        # Knowledge snapshot in April: obs:2 known, preferred
        snap_apr = g.build_snapshot("2026-04-01T00:00:00Z", mode="knowledge")
        assert snap_apr.observation("a", "capacity").value == 120


class TestCounterfactualImmutability:
    """P0.4: Counterfactuals must not modify original snapshot."""

    def test_with_override_preserves_original(self):
        g = Graph()
        g.add(Node(id="a", kind="k", label="A"))
        g.add(Observation(
            id="obs:1", subject="a", metric="capacity", value=100, unit="u",
            effective_at="2026-01-01T00:00:00Z", observed_at="2026-01-01T00:00:00Z",
            source_dataset="test",
        ))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        scenario = snap.with_override(subject="a", metric="capacity", value=200)

        # Original unchanged
        assert snap.observation("a", "capacity").value == 100
        # Scenario has override
        assert scenario.observation("a", "capacity").value == 200
        # Different observation IDs
        assert snap.observation("a", "capacity").id != scenario.observation("a", "capacity").id


class TestModelHashing:
    """P0.1: Model hash must be from actual file bytes."""

    def test_model_hash_changes_with_file(self):
        """Edit one byte of model file -> model_hash changes."""
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(__file__).parent.parent / "models" / "examples" / "pressure_v1.py"
            dst = Path(tmp) / "model.py"
            shutil.copy(src, dst)
            h1 = hash_file(str(dst))
            # Edit one byte
            content = dst.read_text()
            dst.write_text(content.replace("1.0", "1.1"))
            h2 = hash_file(str(dst))
            assert h1 != h2

    def test_model_hash_stable_for_identical_file(self):
        """Identical model file -> stable hash."""
        import tempfile, shutil
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(__file__).parent.parent / "models" / "examples" / "pressure_v1.py"
            dst = Path(tmp) / "model.py"
            shutil.copy(src, dst)
            h1 = hash_file(str(dst))
            h2 = hash_file(str(dst))
            assert h1 == h2


class TestDeterministicDerivation:
    """Same snapshot + same model bytes = same derivation."""

    def test_deterministic_output(self):
        g = load_json(str(FIXTURES / "uk_grid.json"))
        snap = g.build_snapshot("2026-09-01T00:00:00Z")
        from models.examples.pressure_v1 import PressureV1
        m1 = PressureV1()
        m2 = PressureV1()
        d1 = m1.compute(snap)
        d2 = m2.compute(snap)
        assert len(d1) == len(d2)
        for a, b in zip(d1, d2):
            assert a.id == b.id
            assert a.value == b.value
            assert a.unknowns == b.unknowns
