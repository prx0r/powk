"""POWKernel CLI.

Usage:
    pow snapshot --at <time> [--mode world|knowledge] <fixture>
    pow deps <node_id> <fixture>
    pow unknowns <fixture>
    pow path <source> <target> <fixture>
    pow run-model <model_path> <fixture> [--at <time>]
    pow shock <node_id> <metric> <value> <fixture> [--at <time>]
    pow stats <fixture>
"""

import argparse
import json
import sys
import hashlib
from pathlib import Path


def cmd_snapshot(args):
    from pow import Graph
    g = load_fixture(args.fixture)
    snap = g.build_snapshot(args.at, mode=args.mode)
    print(json.dumps(snap.to_dict(), indent=2))


def cmd_deps(args):
    from pow import Graph
    g = load_fixture(args.fixture)
    snap = g.build_snapshot(args.at or "2099-01-01")
    node = snap.node(args.node_id)
    if not node:
        print(f"Node '{args.node_id}' not found")
        sys.exit(1)
    print(f"\n  {args.node_id} ({node.label})")
    print(f"  {'='*60}")
    print(f"\n  Upstream (what it depends on):")
    for nid in snap.upstream(args.node_id):
        n = snap.node(nid)
        label = n.label if n else "?"
        print(f"    <- {nid} ({label})")
    print(f"\n  Downstream (what depends on it):")
    for nid in snap.downstream(args.node_id):
        n = snap.node(nid)
        label = n.label if n else "?"
        print(f"    -> {nid} ({label})")
    print()


def cmd_unknowns(args):
    from pow import Graph, unknowns
    g = load_fixture(args.fixture)
    snap = g.build_snapshot(args.at or "2099-01-01")
    result = unknowns(snap)
    print(f"\n  {'NODE':<30} {'KIND':<15} {'MISSING'}")
    print(f"  {'─'*30} {'─'*15} {'─'*30}")
    for u in result:
        missing = ", ".join(u["missing"]) if u["missing"] else "—"
        print(f"  {u['node']:<30} {u['kind']:<15} {missing}")
    print(f"\n  {len([u for u in result if u['missing']])} nodes with gaps")
    print()


def cmd_path(args):
    from pow import Graph
    g = load_fixture(args.fixture)
    snap = g.build_snapshot(args.at or "2099-01-01")
    paths = snap.paths(args.source, args.target)
    if not paths:
        print(f"  No path from {args.source} to {args.target}")
    else:
        print(f"\n  Paths from {args.source} to {args.target}:")
        for i, p in enumerate(paths):
            print(f"  {' → '.join(p)}")
    print()


def cmd_run_model(args):
    from pow import Graph
    g = load_fixture(args.fixture)
    snap = g.build_snapshot(args.at or "2099-01-01")

    # Load model
    model_path = Path(args.model_path)
    import importlib.util
    spec = importlib.util.spec_from_file_location("model_module", str(model_path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Find Model subclass
    from pow.model_base import Model
    model = None
    for attr in dir(mod):
        obj = getattr(mod, attr)
        if isinstance(obj, type) and issubclass(obj, Model) and obj is not Model:
            model = obj()
            break

    if not model:
        print(f"No Model subclass found in {args.model_path}")
        sys.exit(1)

    derivations = model.compute(snap)
    print(json.dumps([d.to_dict() for d in derivations], indent=2))


def cmd_shock(args):
    from pow import Graph
    g = load_fixture(args.fixture)
    at = args.at or "2099-01-01"
    snap = g.build_snapshot(at)

    # Create counterfactual snapshot
    scenario = snap.with_override(
        subject=args.node_id,
        metric=args.metric,
        value=float(args.value),
    )

    # Run same model as compute
    from models.examples.pressure_v1 import PressureV1
    model = PressureV1()

    original = model.compute(snap)
    counterfactual = model.compute(scenario)

    print(f"\n  Shock: set {args.node_id}.{args.metric} = {args.value}")
    print(f"\n  {'EDGE':<30} {'ORIGINAL':<15} {'SHOCKED':<15} {'DELTA'}")
    print(f"  {'─'*30} {'─'*15} {'─'*15} {'─'*15}")
    for o, c in zip(original, counterfactual):
        ov = f"{o.value:.2f}" if o.value is not None else "—"
        cv = f"{c.value:.2f}" if c.value is not None else "—"
        if o.value is not None and c.value is not None:
            delta = c.value - o.value
            dv = f"{delta:+.2f}"
        else:
            dv = "—"
        print(f"  {o.subject:<30} {ov:<15} {cv:<15} {dv}")
    print()


def cmd_stats(args):
    from pow import Graph
    g = load_fixture(args.fixture)
    stats = g.stats()
    print(f"\n  Fixture: {args.fixture}")
    for k, v in stats.items():
        print(f"    {k}: {v}")
    print()


def load_fixture(path):
    from pow import Graph
    g = Graph()
    g.load_fixture(path)
    return g


def main():
    parser = argparse.ArgumentParser(prog="pow", description="POWKernel CLI")
    sub = parser.add_subparsers(dest="command")

    # snapshot
    p = sub.add_parser("snapshot", help="Build a dated snapshot")
    p.add_argument("fixture", help="Path to fixture JSON")
    p.add_argument("--at", required=True, help="ISO timestamp")
    p.add_argument("--mode", default="world", choices=["world", "knowledge"])

    # deps
    p = sub.add_parser("deps", help="Show upstream/downstream dependencies")
    p.add_argument("node_id", help="Node ID")
    p.add_argument("fixture", help="Path to fixture JSON")
    p.add_argument("--at", help="ISO timestamp")

    # unknowns
    p = sub.add_parser("unknowns", help="Report missing data")
    p.add_argument("fixture", help="Path to fixture JSON")
    p.add_argument("--at", help="ISO timestamp")

    # path
    p = sub.add_parser("path", help="Find paths between nodes")
    p.add_argument("source", help="Source node ID")
    p.add_argument("target", help="Target node ID")
    p.add_argument("fixture", help="Path to fixture JSON")
    p.add_argument("--at", help="ISO timestamp")

    # run-model
    p = sub.add_parser("run-model", help="Run a model against a fixture")
    p.add_argument("model_path", help="Path to model Python file")
    p.add_argument("fixture", help="Path to fixture JSON")
    p.add_argument("--at", help="ISO timestamp")

    # shock
    p = sub.add_parser("shock", help="Simulate a counterfactual shock")
    p.add_argument("node_id", help="Node to shock")
    p.add_argument("metric", help="Metric to override")
    p.add_argument("value", help="New value")
    p.add_argument("fixture", help="Path to fixture JSON")
    p.add_argument("--at", help="ISO timestamp")

    # stats
    p = sub.add_parser("stats", help="Show fixture statistics")
    p.add_argument("fixture", help="Path to fixture JSON")

    args = parser.parse_args()

    cmds = {
        "snapshot": cmd_snapshot,
        "deps": cmd_deps,
        "unknowns": cmd_unknowns,
        "path": cmd_path,
        "run-model": cmd_run_model,
        "shock": cmd_shock,
        "stats": cmd_stats,
    }

    if args.command in cmds:
        cmds[args.command](args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
