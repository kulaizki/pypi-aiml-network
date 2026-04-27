"""Sanity checks against the constructed graphs and analysis outputs (both variants)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import networkx as nx

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT_ROOT = ROOT / "outputs"
VARIANTS = ("required_only", "with_optional")


def assert_(cond: bool, msg: str) -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {msg}")
    if not cond:
        sys.exit(1)


def check_graph(variant: str) -> None:
    print(f"\n=== {variant} ===")
    g = nx.read_gml(DATA / f"graph_{variant}.gml")
    print(f"Graph: {g.number_of_nodes()} nodes, {g.number_of_edges()} edges")

    for pkg in ["torch", "numpy", "pandas", "scikit-learn", "transformers"]:
        assert_(pkg in g, f"node exists: {pkg}")

    known_edges = [
        ("pandas", "numpy"),
        ("scikit-learn", "numpy"),
        ("torchvision", "torch"),
        ("transformers", "huggingface-hub"),
        ("matplotlib", "numpy"),
    ]
    for u, v in known_edges:
        if u in g and v in g:
            assert_(g.has_edge(u, v), f"edge: {u} -> {v}")
        else:
            print(f"[SKIP] {u} -> {v} (endpoint missing)")

    numpy_in = g.in_degree("numpy")
    print(f"numpy in-degree: {numpy_in}")
    assert_(numpy_in > 30, f"numpy in-degree > 30 (got {numpy_in})")

    self_loops = list(nx.selfloop_edges(g))
    assert_(len(self_loops) == 0, f"no self loops (got {len(self_loops)})")

    largest = max(nx.weakly_connected_components(g), key=len)
    pct = 100 * len(largest) / g.number_of_nodes()
    print(f"Largest WCC: {len(largest)} ({pct:.1f}%)")
    assert_(pct > 50, "largest WCC > 50%")

    od = OUT_ROOT / variant
    stats = json.loads((od / "macro_stats.json").read_text())
    assert_(stats["nodes"] == g.number_of_nodes(), "macro nodes match")
    assert_(stats["edges"] == g.number_of_edges(), "macro edges match")

    rq1 = json.loads((od / "rq1_bottlenecks.json").read_text())
    for name, _ in rq1["top_betweenness"][:10]:
        assert_(name in g, f"RQ1 top node in graph: {name}")

    rq2_mem = json.loads((od / "rq2_membership.json").read_text())
    assert_(len(rq2_mem) == g.number_of_nodes(), "RQ2 membership covers all nodes")

    rq3 = json.loads((od / "rq3_fragility.json").read_text())
    pcts = [t["orphan_pct"] for t in rq3["trials"]]
    monotone = all(b >= a - 1e-9 for a, b in zip(pcts, pcts[1:]))
    assert_(monotone, f"RQ3 monotone: {pcts}")


def check_comparison() -> None:
    print("\n=== comparison ===")
    cmp_dir = OUT_ROOT / "comparison"
    summary = json.loads((cmp_dir / "summary.json").read_text())
    assert_(len(summary) == 2, "comparison has 2 variants")
    by_v = {r["variant"]: r for r in summary}

    # Variant invariants
    assert_(by_v["required_only"]["is_dag"] is True, "required_only is a DAG")
    # required-only should be more brittle per node
    ro_pct = by_v["required_only"]["orphan_pct@k=50"]
    wo_pct = by_v["with_optional"]["orphan_pct@k=50"]
    print(f"orphan@k=50: required_only={ro_pct}%  with_optional={wo_pct}%")
    assert_(ro_pct > wo_pct, "required_only more brittle than with_optional at k=50")

    # Files exist
    for f in ("rq1_bottlenecks_compare.png", "rq3_fragility_overlay.png", "summary.md"):
        assert_((cmp_dir / f).exists(), f"comparison artifact: {f}")


def main() -> None:
    for v in VARIANTS:
        check_graph(v)
    check_comparison()
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
