"""Charts (matplotlib) + interactive HTML graph (pyvis), per variant."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import networkx as nx
from pyvis.network import Network

from .build_graph import VARIANTS, graph_path

OUT_ROOT = Path(__file__).resolve().parents[1] / "outputs"

CATEGORY_COLORS = {
    "deep_learning": "#e74c3c",
    "nlp": "#9b59b6",
    "classical_ml": "#f39c12",
    "data": "#3498db",
    "viz": "#1abc9c",
    "cv": "#e67e22",
    "mlops": "#2ecc71",
    "other": "#95a5a6",
}


def variant_paths(variant: str) -> tuple[Path, Path, Path]:
    base = OUT_ROOT / variant
    fig = base / "figures"
    html = base / "html"
    fig.mkdir(parents=True, exist_ok=True)
    html.mkdir(parents=True, exist_ok=True)
    return base, fig, html


def degree_distribution(g: nx.DiGraph, fig_dir: Path, variant: str) -> None:
    in_deg = [d for _, d in g.in_degree()]
    out_deg = [d for _, d in g.out_degree()]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for ax, data, label in zip(axes, (in_deg, out_deg), ("in-degree", "out-degree")):
        c = Counter(data)
        xs, ys = zip(*sorted(c.items()))
        ax.scatter(xs, ys, s=12, alpha=0.7)
        ax.set_xscale("symlog")
        ax.set_yscale("symlog")
        ax.set_xlabel(label)
        ax.set_ylabel("count of nodes")
        ax.set_title(f"[{variant}] {label} distribution")
        ax.grid(True, which="both", linestyle=":", alpha=0.3)
    fig.tight_layout()
    fig.savefig(fig_dir / "degree_distribution.png", dpi=140)
    plt.close(fig)


def bottleneck_bar(rq1_path: Path, fig_dir: Path, variant: str, top: int = 20) -> None:
    rq1 = json.loads(rq1_path.read_text())
    items = rq1["top_betweenness"][:top]
    names = [n for n, _ in items][::-1]
    vals = [v for _, v in items][::-1]
    fig, ax = plt.subplots(figsize=(8, 0.35 * top + 1))
    ax.barh(names, vals, color="#c0392b")
    ax.set_xlabel("betweenness centrality")
    ax.set_title(f"RQ1: Top {top} bottlenecks [{variant}]")
    fig.tight_layout()
    fig.savefig(fig_dir / "rq1_top_betweenness.png", dpi=140)
    plt.close(fig)


def fragility_curve(rq3_path: Path, fig_dir: Path, variant: str) -> None:
    rq3 = json.loads(rq3_path.read_text())
    ks = [t["k"] for t in rq3["trials"]]
    pct = [t["orphan_pct"] for t in rq3["trials"]]
    fig, ax = plt.subplots(figsize=(7, 4.2))
    ax.plot(ks, pct, marker="o", color="#8e44ad", linewidth=2)
    ax.set_xlabel("k (top-k removed by betweenness)")
    ax.set_ylabel("% of largest WCC fragmented")
    ax.set_title(f"RQ3: Cascade fragility [{variant}]")
    ax.grid(True, linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(fig_dir / "rq3_fragility_curve.png", dpi=140)
    plt.close(fig)


def interactive_graph(
    g: nx.DiGraph, membership_path: Path, rq1_path: Path,
    html_dir: Path, variant: str, max_nodes: int = 400,
) -> None:
    rq1 = json.loads(rq1_path.read_text())
    btwn = dict(rq1["top_betweenness"])
    top_in = sorted(g.in_degree(), key=lambda kv: kv[1], reverse=True)[: max_nodes // 2]
    keep = set(n for n, _ in top_in) | set(list(btwn.keys())[: max_nodes // 2])
    keep &= set(g.nodes())
    sub = g.subgraph(keep).copy()
    membership = json.loads(membership_path.read_text())
    net = Network(
        height="800px", width="100%", directed=True,
        bgcolor="#101418", font_color="#e6e6e6",
        notebook=False, cdn_resources="in_line",
    )
    for n, attrs in sub.nodes(data=True):
        cat = attrs.get("category", "other")
        color = CATEGORY_COLORS.get(cat, "#95a5a6")
        size = 10 + 25 * (sub.in_degree(n) ** 0.5) / max(1, sub.number_of_nodes() ** 0.25)
        title = (
            f"{n}\ncategory: {cat}\nin_degree: {sub.in_degree(n)}\n"
            f"out_degree: {sub.out_degree(n)}\ncommunity: {membership.get(n, '?')}"
        )
        net.add_node(n, label=n, color=color, size=size, title=title)
    for u, v in sub.edges():
        net.add_edge(u, v, color="#3a3f47")
    net.set_options(
        '{"physics":{"barnesHut":{"gravitationalConstant":-12000,"springLength":120},'
        '"minVelocity":0.6,"stabilization":{"iterations":250}}}'
    )
    net.save_graph(str(html_dir / "network.html"))


def run(variant: str) -> None:
    base, fig_dir, html_dir = variant_paths(variant)
    g = nx.read_gml(graph_path(variant))
    print(f"[{variant}] visualizing {g.number_of_nodes()} nodes")
    degree_distribution(g, fig_dir, variant)
    bottleneck_bar(base / "rq1_bottlenecks.json", fig_dir, variant)
    fragility_curve(base / "rq3_fragility.json", fig_dir, variant)
    interactive_graph(g, base / "rq2_membership.json", base / "rq1_bottlenecks.json",
                      html_dir, variant)


def main(variant: str | None = None) -> None:
    targets = [variant] if variant else list(VARIANTS)
    for v in targets:
        run(v)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=VARIANTS, default=None)
    args = ap.parse_args()
    main(args.variant)
