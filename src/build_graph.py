"""Build a directed dependency graph from cached PyPI metadata.

Two variants:
  - required_only: only required deps; runtime view; expected to be a DAG.
  - with_optional: includes extras_require; full developer-surface view.

Both use the same on-disk cache (data/cache/) so no re-fetching is needed
once a superset crawl has populated it.
"""
from __future__ import annotations

import argparse
import json
from collections import deque
from pathlib import Path

import networkx as nx

from .collect import CACHE_DIR, normalize, parse_requires
from .seeds import all_seeds, category_of

DATA_DIR = Path(__file__).resolve().parents[1] / "data"

VARIANTS = ("required_only", "with_optional")


def graph_path(variant: str) -> Path:
    return DATA_DIR / f"graph_{variant}.gml"


def load_cached() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for p in CACHE_DIR.glob("*.json"):
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError:
            continue
        out[p.stem] = data
    return out


def reachable_from_seeds(
    meta_by_name: dict[str, dict],
    include_optional: bool,
) -> set[str]:
    """BFS from seeds through cache, following only edges allowed by the variant."""
    reachable: set[str] = set()
    q: deque[str] = deque()
    for s in all_seeds():
        n = normalize(s)
        if n not in reachable:
            reachable.add(n)
            q.append(n)
    while q:
        name = q.popleft()
        meta = meta_by_name.get(name)
        if not meta or meta.get("_missing"):
            continue
        for dep_name, attrs in parse_requires(meta):
            if attrs["optional"] and not include_optional:
                continue
            if dep_name not in reachable:
                reachable.add(dep_name)
                q.append(dep_name)
    return reachable


def build(meta_by_name: dict[str, dict], include_optional: bool) -> nx.DiGraph:
    keep = reachable_from_seeds(meta_by_name, include_optional)
    g = nx.DiGraph()
    for name in keep:
        meta = meta_by_name.get(name)
        if not meta or meta.get("_missing"):
            g.add_node(
                name,
                summary="",
                version="",
                weekly_downloads=-1,
                category=category_of(name) or "other",
                stub=True,
            )
            continue
        info = meta.get("info") or {}
        downloads = info.get("downloads") or {}
        weekly = downloads.get("last_week", -1) if isinstance(downloads, dict) else -1
        g.add_node(
            name,
            summary=(info.get("summary") or "")[:200],
            version=info.get("version") or "",
            weekly_downloads=int(weekly) if isinstance(weekly, (int, float)) else -1,
            category=category_of(name) or "other",
        )
    for name in keep:
        meta = meta_by_name.get(name)
        if not meta or meta.get("_missing"):
            continue
        for dep_name, attrs in parse_requires(meta):
            if attrs["optional"] and not include_optional:
                continue
            if dep_name not in keep:
                continue
            if name == dep_name:  # avoid self-loops
                continue
            g.add_edge(
                name, dep_name,
                specifier=attrs["specifier"],
                pinned=attrs["pinned"],
                optional=attrs["optional"],
            )
    return g


def main(variant: str | None = None) -> None:
    meta = load_cached()
    targets = [variant] if variant else list(VARIANTS)
    for v in targets:
        include_optional = v == "with_optional"
        g = build(meta, include_optional=include_optional)
        out = graph_path(v)
        out.parent.mkdir(parents=True, exist_ok=True)
        nx.write_gml(g, out)
        print(
            f"[{v}] nodes={g.number_of_nodes()} edges={g.number_of_edges()} "
            f"is_dag={nx.is_directed_acyclic_graph(g)}  -> {out}"
        )


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=VARIANTS, default=None,
                    help="Default: build both variants.")
    args = ap.parse_args()
    main(args.variant)
