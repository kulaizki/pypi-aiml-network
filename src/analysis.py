"""RQ1 (bottlenecks), RQ2 (communities), RQ3 (fragility cascade)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import networkx as nx

from .build_graph import VARIANTS, graph_path

OUT_ROOT = Path(__file__).resolve().parents[1] / "outputs"


def out_dir(variant: str) -> Path:
    p = OUT_ROOT / variant
    p.mkdir(parents=True, exist_ok=True)
    return p


def macro_stats(g: nx.DiGraph) -> dict:
    ug = g.to_undirected()
    largest_wcc = max(nx.weakly_connected_components(g), key=len)
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "density": nx.density(g),
        "is_dag": nx.is_directed_acyclic_graph(g),
        "n_weak_components": nx.number_weakly_connected_components(g),
        "largest_wcc_size": len(largest_wcc),
        "avg_clustering_undirected": nx.average_clustering(ug),
        "avg_in_degree": sum(d for _, d in g.in_degree()) / max(g.number_of_nodes(), 1),
    }


def rq1_bottlenecks(g: nx.DiGraph, top_k: int = 25) -> dict:
    largest_wcc = max(nx.weakly_connected_components(g), key=len)
    sub = g.subgraph(largest_wcc).copy()
    btwn = nx.betweenness_centrality(sub, normalized=True)
    in_deg = nx.in_degree_centrality(g)
    out_deg = nx.out_degree_centrality(g)
    closeness = nx.closeness_centrality(sub)

    def topk(d: dict, k: int = top_k) -> list[tuple[str, float]]:
        return sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:k]

    return {
        "top_betweenness": topk(btwn),
        "top_in_degree": topk(in_deg),
        "top_out_degree": topk(out_deg),
        "top_closeness": topk(closeness),
    }


def rq2_communities(g: nx.DiGraph, seed: int = 42) -> dict:
    ug = g.to_undirected()
    communities = nx.community.louvain_communities(ug, seed=seed)
    communities.sort(key=len, reverse=True)
    modularity = nx.community.modularity(ug, communities)
    membership = {n: i for i, c in enumerate(communities) for n in c}
    sizes = [len(c) for c in communities]
    samples = [sorted(list(c))[:15] for c in communities[:10]]
    return {
        "n_communities": len(communities),
        "modularity": modularity,
        "sizes_top20": sizes[:20],
        "samples_top10": samples,
        "membership": membership,
    }


def rq3_fragility(g: nx.DiGraph, ks: list[int] | None = None) -> dict:
    ks = ks or [1, 3, 5, 10, 20, 30, 50]
    largest_wcc = max(nx.weakly_connected_components(g), key=len)
    sub = g.subgraph(largest_wcc).copy()
    btwn = nx.betweenness_centrality(sub, normalized=True)
    ranked = [n for n, _ in sorted(btwn.items(), key=lambda kv: kv[1], reverse=True)]

    base_largest = len(largest_wcc)
    results: list[dict] = []
    for k in ks:
        h = g.copy()
        removed = ranked[:k]
        h.remove_nodes_from(removed)
        if h.number_of_nodes() == 0:
            results.append({
                "k": k, "removed": removed, "remaining_nodes": 0,
                "largest_wcc": 0, "n_wcc": 0, "orphan_pct": 100.0,
            })
            continue
        new_largest = max((len(c) for c in nx.weakly_connected_components(h)), default=0)
        n_wcc = nx.number_weakly_connected_components(h)
        orphan_pct = 100.0 * (1 - new_largest / base_largest)
        results.append({
            "k": k, "removed": removed,
            "remaining_nodes": h.number_of_nodes(),
            "largest_wcc": new_largest, "n_wcc": n_wcc,
            "orphan_pct": orphan_pct,
        })
    return {"baseline_nodes": g.number_of_nodes(), "baseline_largest_wcc": base_largest,
            "trials": results}


def run(variant: str) -> None:
    g = nx.read_gml(graph_path(variant))
    od = out_dir(variant)
    print(f"\n=== [{variant}] {g.number_of_nodes()} nodes, {g.number_of_edges()} edges ===")

    stats = macro_stats(g)
    (od / "macro_stats.json").write_text(json.dumps(stats, indent=2))
    print("macro:", stats)

    rq1 = rq1_bottlenecks(g)
    (od / "rq1_bottlenecks.json").write_text(json.dumps(rq1, indent=2))
    print("RQ1 top-betweenness:", [n for n, _ in rq1["top_betweenness"][:10]])

    rq2 = rq2_communities(g)
    rq2_save = {k: v for k, v in rq2.items() if k != "membership"}
    (od / "rq2_communities.json").write_text(json.dumps(rq2_save, indent=2))
    (od / "rq2_membership.json").write_text(json.dumps(rq2["membership"], indent=2))
    print(f"RQ2: {rq2['n_communities']} communities, modularity={rq2['modularity']:.4f}")

    rq3 = rq3_fragility(g)
    (od / "rq3_fragility.json").write_text(json.dumps(rq3, indent=2))
    for t in rq3["trials"]:
        print(
            f"  k={t['k']:>3} -> largest_wcc={t['largest_wcc']} "
            f"({t['orphan_pct']:.1f}% orphaned)"
        )


def main(variant: str | None = None) -> None:
    targets = [variant] if variant else list(VARIANTS)
    for v in targets:
        run(v)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=VARIANTS, default=None)
    args = ap.parse_args()
    main(args.variant)
