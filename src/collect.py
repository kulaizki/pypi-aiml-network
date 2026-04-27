"""BFS crawl of PyPI JSON API starting from AI/ML seeds, with disk cache."""
from __future__ import annotations

import json
import re
import time
from collections import deque
from pathlib import Path
from typing import Iterable

import requests
from packaging.requirements import InvalidRequirement, Requirement
from tqdm import tqdm

from .seeds import all_seeds

PYPI_URL = "https://pypi.org/pypi/{name}/json"
USER_AGENT = "pypi-aiml-network/0.1 (research)"
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache"
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def normalize(name: str) -> str:
    """PEP 503 normalized package name."""
    return re.sub(r"[-_.]+", "-", name).lower()


def cache_path(name: str) -> Path:
    safe = normalize(name)
    return CACHE_DIR / f"{safe}.json"


def fetch_one(name: str, session: requests.Session, sleep: float = 0.0) -> dict | None:
    """Fetch package metadata, using on-disk cache. Returns None on 404."""
    p = cache_path(name)
    if p.exists():
        try:
            return json.loads(p.read_text())
        except json.JSONDecodeError:
            p.unlink(missing_ok=True)
    if sleep:
        time.sleep(sleep)
    try:
        r = session.get(PYPI_URL.format(name=name), timeout=15)
    except requests.RequestException:
        return None
    if r.status_code == 404:
        p.write_text(json.dumps({"_missing": True, "name": name}))
        return {"_missing": True, "name": name}
    if r.status_code != 200:
        return None
    data = r.json()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data))
    return data


def parse_requires(meta: dict) -> list[tuple[str, dict]]:
    """Extract (dep_name, attrs) from requires_dist. Skips extras (optional deps)."""
    info = meta.get("info") or {}
    raw = info.get("requires_dist") or []
    out: list[tuple[str, dict]] = []
    for spec in raw:
        if not isinstance(spec, str) or not spec.strip():
            continue
        try:
            req = Requirement(spec)
        except InvalidRequirement:
            continue
        is_extra = bool(req.marker) and "extra" in str(req.marker)
        specifier = str(req.specifier) if req.specifier else ""
        attrs = {
            "specifier": specifier,
            "pinned": bool(req.specifier and any(s.operator == "==" for s in req.specifier)),
            "optional": is_extra,
            "marker": str(req.marker) if req.marker else "",
        }
        if NAME_RE.match(req.name or ""):
            out.append((normalize(req.name), attrs))
    return out


def bfs(
    seeds: Iterable[str],
    max_nodes: int = 3000,
    max_depth: int = 4,
    include_optional: bool = False,
    sleep: float = 0.05,
) -> dict[str, dict]:
    """BFS over PyPI dependency graph. Returns dict of normalized_name -> metadata."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept": "application/json"})

    fetched: dict[str, dict] = {}
    depth: dict[str, int] = {}
    q: deque[str] = deque()
    for s in seeds:
        n = normalize(s)
        if n not in depth:
            depth[n] = 0
            q.append(n)

    pbar = tqdm(total=max_nodes, desc="crawl")
    while q and len(fetched) < max_nodes:
        name = q.popleft()
        if name in fetched:
            continue
        meta = fetch_one(name, session, sleep=sleep)
        if meta is None:
            continue
        fetched[name] = meta
        pbar.update(1)
        if meta.get("_missing"):
            continue
        if depth[name] >= max_depth:
            continue
        for dep_name, attrs in parse_requires(meta):
            if attrs["optional"] and not include_optional:
                continue
            if dep_name not in depth:
                depth[dep_name] = depth[name] + 1
                q.append(dep_name)
    pbar.close()
    return fetched


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--max-nodes", type=int, default=3000)
    ap.add_argument("--max-depth", type=int, default=4)
    ap.add_argument("--include-optional", action="store_true")
    ap.add_argument("--sleep", type=float, default=0.05)
    args = ap.parse_args()

    fetched = bfs(
        all_seeds(),
        max_nodes=args.max_nodes,
        max_depth=args.max_depth,
        include_optional=args.include_optional,
        sleep=args.sleep,
    )
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    summary = {
        "n_fetched": len(fetched),
        "n_missing": sum(1 for m in fetched.values() if m.get("_missing")),
        "seeds": all_seeds(),
        "args": vars(args),
    }
    (RAW_DIR / "crawl_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
