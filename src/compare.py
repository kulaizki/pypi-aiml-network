"""Side-by-side comparison: required-only vs with-optional."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .build_graph import VARIANTS

OUT_ROOT = Path(__file__).resolve().parents[1] / "outputs"
CMP_DIR = OUT_ROOT / "comparison"


def load(variant: str, name: str) -> dict:
    return json.loads((OUT_ROOT / variant / name).read_text())


def bottleneck_side_by_side(top: int = 15) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14, 0.35 * top + 1.5), sharex=False)
    for ax, variant in zip(axes, VARIANTS):
        rq1 = load(variant, "rq1_bottlenecks.json")
        items = rq1["top_betweenness"][:top]
        names = [n for n, _ in items][::-1]
        vals = [v for _, v in items][::-1]
        color = "#16a085" if variant == "required_only" else "#c0392b"
        ax.barh(names, vals, color=color)
        ax.set_xlabel("betweenness centrality")
        ax.set_title(f"Top {top} bottlenecks ({variant})")
    fig.suptitle("RQ1: Bottleneck comparison (production runtime vs developer surface)",
                 fontsize=12)
    fig.tight_layout()
    fig.savefig(CMP_DIR / "rq1_bottlenecks_compare.png", dpi=140)
    plt.close(fig)


def fragility_overlay() -> None:
    fig, ax = plt.subplots(figsize=(8, 5))
    palette = {"required_only": "#16a085", "with_optional": "#c0392b"}
    for variant in VARIANTS:
        rq3 = load(variant, "rq3_fragility.json")
        ks = [t["k"] for t in rq3["trials"]]
        pct = [t["orphan_pct"] for t in rq3["trials"]]
        ax.plot(ks, pct, marker="o", linewidth=2,
                label=f"{variant} (N={rq3['baseline_largest_wcc']})",
                color=palette[variant])
    ax.set_xlabel("k (top-k removed by betweenness)")
    ax.set_ylabel("% of largest WCC fragmented")
    ax.set_title("RQ3: Cascade fragility (runtime is more brittle per node)")
    ax.legend()
    ax.grid(True, linestyle=":", alpha=0.4)
    fig.tight_layout()
    fig.savefig(CMP_DIR / "rq3_fragility_overlay.png", dpi=140)
    plt.close(fig)


def summary_table() -> None:
    rows: list[dict] = []
    for variant in VARIANTS:
        macro = load(variant, "macro_stats.json")
        rq1 = load(variant, "rq1_bottlenecks.json")
        rq2 = load(variant, "rq2_communities.json")
        rq3 = load(variant, "rq3_fragility.json")
        last = rq3["trials"][-1]
        rows.append({
            "variant": variant,
            "nodes": macro["nodes"],
            "edges": macro["edges"],
            "is_dag": macro["is_dag"],
            "largest_wcc": macro["largest_wcc_size"],
            "avg_clustering": round(macro["avg_clustering_undirected"], 4),
            "n_communities": rq2["n_communities"],
            "modularity": round(rq2["modularity"], 4),
            "top1_bottleneck": rq1["top_betweenness"][0][0],
            f"orphan_pct@k={last['k']}": round(last["orphan_pct"], 2),
        })
    (CMP_DIR / "summary.json").write_text(json.dumps(rows, indent=2))

    # Markdown table
    cols = list(rows[0].keys())
    md = ["| " + " | ".join(cols) + " |",
          "| " + " | ".join(["---"] * len(cols)) + " |"]
    for r in rows:
        md.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    (CMP_DIR / "summary.md").write_text("\n".join(md) + "\n")
    print("\n".join(md))


def main() -> None:
    CMP_DIR.mkdir(parents=True, exist_ok=True)
    summary_table()
    bottleneck_side_by_side()
    fragility_overlay()
    print(f"\nWrote comparison artifacts to: {CMP_DIR}")


if __name__ == "__main__":
    main()
