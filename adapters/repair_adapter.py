"""repair adapter — export Layer 1 data to powk canonical format.

Reads from:
  warehouse/repair.db — source_record table (305K open_repair records)

Exports to powk JSONL:
  nodes.jsonl
  edges.jsonl
  observations.jsonl
  evidence.jsonl
"""

import json
import sqlite3
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pow.canonical import make_id
from pow.model import (
    Node, Edge, Observation, Evidence,
    make_edge_id, make_obs_id, make_ev_id,
)

EXPORT_DIR = Path("/home/ubuntu/powk/exports/repair")
DB_PATH = Path("/home/ubuntu/repair/warehouse/repair.db")


def export_nodes():
    """Export device categories and fault types as NODEs."""
    nodes = []

    if not DB_PATH.exists():
        print(f"  Warning: DB not found at {DB_PATH}")
        return nodes

    conn = sqlite3.connect(str(DB_PATH))

    # Get distinct product categories
    rows = conn.execute("""
        SELECT DISTINCT json_extract(normalized_json, '$.product_category')
        FROM source_record WHERE source_id = 'open_repair'
        AND json_extract(normalized_json, '$.product_category') IS NOT NULL
    """).fetchall()
    for (category,) in rows:
        if category:
            nodes.append(Node(
                id=f"repair:category:{category.lower().replace(' ', '_')}",
                kind="category",
                label=category,
            ))

    # Get distinct fault types
    rows = conn.execute("""
        SELECT DISTINCT json_extract(normalized_json, '$.problem')
        FROM source_record WHERE source_id = 'open_repair'
        AND json_extract(normalized_json, '$.problem') IS NOT NULL
        LIMIT 200
    """).fetchall()
    seen_problems = set()
    for (problem,) in rows:
        if problem and problem not in seen_problems:
            seen_problems.add(problem)
            # Normalize problem to a short key
            key = problem.lower().strip()[:50].replace(' ', '_').replace('/', '_')
            nodes.append(Node(
                id=f"repair:fault:{key}",
                kind="fault",
                label=problem[:100],
            ))

    # Get distinct brands
    rows = conn.execute("""
        SELECT DISTINCT json_extract(normalized_json, '$.brand')
        FROM source_record WHERE source_id = 'open_repair'
        AND json_extract(normalized_json, '$.brand') IS NOT NULL
        LIMIT 100
    """).fetchall()
    for (brand,) in rows:
        if brand:
            nodes.append(Node(
                id=f"repair:brand:{brand.lower().replace(' ', '_')}",
                kind="brand",
                label=brand,
            ))

    conn.close()
    return nodes


def export_edges(nodes):
    """Export REQUIRES edges: category -> brand, brand -> fault."""
    edges = []
    node_ids = {n.id for n in nodes}

    # Sample edges: category requires brand (brands make products in categories)
    # This is a simplification — real edges would come from asset-fault mappings
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute("""
        SELECT DISTINCT
            json_extract(normalized_json, '$.product_category'),
            json_extract(normalized_json, '$.brand'),
            json_extract(normalized_json, '$.problem')
        FROM source_record WHERE source_id = 'open_repair'
        AND json_extract(normalized_json, '$.product_category') IS NOT NULL
        AND json_extract(normalized_json, '$.brand') IS NOT NULL
        LIMIT 500
    """).fetchall()
    conn.close()

    seen_edges = set()
    for category, brand, problem in rows:
        if not category or not brand:
            continue
        cat_id = f"repair:category:{category.lower().replace(' ', '_')}"
        brand_id = f"repair:brand:{brand.lower().replace(' ', '_')}"

        # brand REQUIRES category (a brand produces in a category)
        edge_key = (brand_id, cat_id)
        if edge_key not in seen_edges and cat_id in node_ids and brand_id in node_ids:
            seen_edges.add(edge_key)
            edges.append(Edge(
                id=make_edge_id(brand_id, cat_id),
                source=brand_id,
                target=cat_id,
                relation="REQUIRES",
            ))

        # brand has fault
        if problem:
            fault_key = problem.lower().strip()[:50].replace(' ', '_').replace('/', '_')
            fault_id = f"repair:fault:{fault_key}"
            edge_key2 = (cat_id, fault_id)
            if edge_key2 not in seen_edges and cat_id in node_ids and fault_id in node_ids:
                seen_edges.add(edge_key2)
                edges.append(Edge(
                    id=make_edge_id(cat_id, fault_id),
                    source=cat_id,
                    target=fault_id,
                    relation="REQUIRES",
                ))

    return edges


def export_observations():
    """Export repair status counts as OBSERVATIONs."""
    observations = []
    now = datetime.now(timezone.utc).isoformat()

    conn = sqlite3.connect(str(DB_PATH))

    # Count repairs by category and status
    rows = conn.execute("""
        SELECT
            json_extract(normalized_json, '$.product_category'),
            json_extract(normalized_json, '$.repair_status'),
            COUNT(*)
        FROM source_record WHERE source_id = 'open_repair'
        GROUP BY 1, 2
    """).fetchall()

    for category, status, count in rows:
        if not category or not status:
            continue
        subject = f"repair:category:{category.lower().replace(' ', '_')}"
        metric = f"repair_count_{status.lower().replace(' ', '_')}"
        observations.append(Observation(
            id=make_obs_id(subject, metric, float(count), "devices", now, now, "repair:open_repair"),
            subject=subject,
            metric=metric,
            value=float(count),
            unit="devices",
            effective_at="2026-01-01T00:00:00Z",  # dataset covers all time
            observed_at=now,
            source_dataset="repair:open_repair",
        ))

    # Total records per category
    rows = conn.execute("""
        SELECT
            json_extract(normalized_json, '$.product_category'),
            COUNT(*)
        FROM source_record WHERE source_id = 'open_repair'
        GROUP BY 1
    """).fetchall()

    for category, count in rows:
        if not category:
            continue
        subject = f"repair:category:{category.lower().replace(' ', '_')}"
        observations.append(Observation(
            id=make_obs_id(subject, "total_repairs", float(count), "devices", now, now, "repair:open_repair"),
            subject=subject,
            metric="total_repairs",
            value=float(count),
            unit="devices",
            effective_at="2026-01-01T00:00:00Z",
            observed_at=now,
            source_dataset="repair:open_repair",
        ))

    conn.close()
    return observations


def export_evidence(observations):
    """Export evidence for observations."""
    evidence = []
    for obs in observations:
        ev_id = make_ev_id(obs.id, "SUPPORTS",
                           f"Open Repair: {obs.subject} {obs.metric}={obs.value}",
                           publisher="Open Repair Alliance")
        evidence.append(Evidence(
            id=ev_id,
            target=obs.id,
            direction="SUPPORTS",
            claim=f"Open Repair Alliance dataset: {obs.metric} = {obs.value}",
            publisher="Open Repair Alliance",
            source_uri="repair:open_repair",
        ))
    return evidence


def export(output_dir=None):
    """Run full export."""
    out = Path(output_dir) if output_dir else EXPORT_DIR
    out.mkdir(parents=True, exist_ok=True)

    print("Exporting repair -> powk format...")

    nodes = export_nodes()
    print(f"  Nodes: {len(nodes)}")

    edges = export_edges(nodes)
    print(f"  Edges: {len(edges)}")

    observations = export_observations()
    print(f"  Observations: {len(observations)}")

    evidence = export_evidence(observations)
    print(f"  Evidence: {len(evidence)}")

    # Write JSONL
    for filename, items in [
        ("nodes.jsonl", nodes),
        ("edges.jsonl", edges),
        ("observations.jsonl", observations),
        ("evidence.jsonl", evidence),
    ]:
        path = out / filename
        with open(path, "w") as f:
            for item in items:
                f.write(json.dumps(item.to_dict(), default=str) + "\n")
        print(f"  Wrote {path}")

    return {"nodes": len(nodes), "edges": len(edges),
            "observations": len(observations), "evidence": len(evidence)}


if __name__ == "__main__":
    result = export()
    print(f"\nDone: {result}")
