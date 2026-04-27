"""Run the full pipeline: collect (once) -> build/analyze/visualize per variant -> compare."""
from __future__ import annotations

import argparse

from src import analysis, build_graph, collect, compare, visualize
from src.build_graph import VARIANTS
from src.seeds import all_seeds


def run(max_nodes: int, max_depth: int, sleep: float, skip_collect: bool) -> None:
    if not skip_collect:
        # One crawl that includes optional deps so cache covers both variants.
        print(f"[1/5] Crawling PyPI (max_nodes={max_nodes}, depth={max_depth}, +optional)...")
        collect.bfs(
            all_seeds(),
            max_nodes=max_nodes,
            max_depth=max_depth,
            include_optional=True,
            sleep=sleep,
        )
    else:
        print("[1/5] Skipping crawl (using cache).")

    print("[2/5] Building graphs (both variants)...")
    build_graph.main()
    for v in VARIANTS:
        print(f"\n[3/5] Analysis [{v}]...")
        analysis.run(v)
        print(f"[4/5] Visualizations [{v}]...")
        visualize.run(v)
    print("\n[5/5] Comparison artifacts...")
    compare.main()
    print("\nDone.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-nodes", type=int, default=3000)
    ap.add_argument("--max-depth", type=int, default=5)
    ap.add_argument("--sleep", type=float, default=0.03)
    ap.add_argument("--skip-collect", action="store_true",
                    help="Reuse existing cache; skip the crawl.")
    args = ap.parse_args()
    run(args.max_nodes, args.max_depth, args.sleep, args.skip_collect)
