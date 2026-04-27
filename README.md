# PyPI AI/ML Network

Network analysis of the Python AI/ML package ecosystem on PyPI. Crawls dependency metadata from a seed of ~50 core AI/ML packages, builds a directed graph, and analyzes structural bottlenecks, communities, and cascade fragility.

## Research questions

1. **RQ1: Bottlenecks.** Which packages are the most critical structural single points of failure? (betweenness centrality)
2. **RQ2: Communities.** What clusters of co-dependent packages exist, and do they map to recognizable AI/ML sub-ecosystems? (Louvain)
3. **RQ3: Fragility.** If the top-k most central packages fail, how much of the ecosystem becomes orphaned? (iterative removal)

## Two views

The same crawl produces two graphs with different stories:

| variant         | scope                                             | answers                  |
| --------------- | ------------------------------------------------- | ------------------------ |
| `required_only` | `Requires-Dist` only (production runtime)         | runtime fragility        |
| `with_optional` | All deps including `extras_require` (dev surface) | full ecosystem fragility |

## Setup

```bash
git clone <repo-url> pypi-aiml-network
cd pypi-aiml-network
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Python 3.10+ recommended (tested on 3.14).

## Run

```bash
# First run: crawl PyPI (~10 min for ~3,000 packages)
python3 main.py

# Subsequent runs: reuse cache, rebuild graphs and analysis (~30s)
python3 main.py --skip-collect

# Verify outputs
python3 scripts/verify.py
```

The crawler is resumable. `data/cache/` is gitignored (~700 MB), so each clone rebuilds it locally on first run.

## Per-stage commands

```bash
python3 -m src.collect --max-nodes 3000 --max-depth 5 --include-optional
python3 -m src.build_graph
python3 -m src.analysis --variant required_only
python3 -m src.visualize --variant with_optional
python3 -m src.compare
```

## Flags

| flag             | default | meaning                              |
| ---------------- | ------- | ------------------------------------ |
| `--max-nodes`    | 3000    | Cap on packages fetched in the crawl |
| `--max-depth`    | 5       | BFS depth from seeds                 |
| `--sleep`        | 0.03    | Per-request sleep, seconds           |
| `--skip-collect` | off     | Skip the crawl, reuse `data/cache/`  |

## Project layout

```
pypi-aiml-network/
├── main.py                       # End-to-end pipeline
├── requirements.txt
├── scripts/verify.py             # Sanity checks on outputs
├── src/
│   ├── seeds.py                  # Seed AI/ML packages, by category
│   ├── collect.py                # PyPI BFS crawler with disk cache
│   ├── build_graph.py            # NetworkX DiGraph (per variant)
│   ├── analysis.py               # RQ1 / RQ2 / RQ3
│   ├── visualize.py              # matplotlib + pyvis
│   └── compare.py                # Side-by-side comparison
├── data/
│   ├── cache/                    # PyPI JSON, per package (gitignored)
│   └── graph_*.gml               # Built graphs (gitignored)
└── outputs/
    ├── required_only/            # macro_stats, rq1, rq2, rq3 + figures + html
    ├── with_optional/            # same structure
    └── comparison/               # side-by-side artifacts
```

## Headline results

| variant         | nodes | edges  | DAG | largest WCC  | modularity | top-1 bottleneck | orphan @ k=50 |
| --------------- | ----- | ------ | --- | ------------ | ---------- | ---------------- | ------------- |
| `required_only` | 266   | 621    | yes | 264 (99%)    | 0.549      | **torch**        | **39.4%**     |
| `with_optional` | 4,777 | 22,780 | no  | 4,777 (100%) | 0.473      | **pandas**       | 24.1%         |

Two views, two stories:

- The **production runtime core** (266 packages) centers on `torch` plus a few HTTP/AI clients. It's a tight DAG that fragments steadily; remove the top 50 packages and 39.4% of the network is orphaned.
- The **developer surface** (4,777 packages) centers on `pandas`, `ipython`, `pytest`, `hypothesis`. It's robust to the first 10 removals (<0.5%), then crosses a knee and plateaus at 24.1% by k=50.
- Pandas is more central to _how_ AI/ML gets built; torch is more central to _what runs in production_. The runtime is brittle but small; the dev surface is large and redundant.

See `outputs/comparison/rq1_bottlenecks_compare.png` and `outputs/comparison/rq3_fragility_overlay.png`.

## Notes

- Some packages return null `requires_dist` from the PyPI JSON API (older uploads). They become leaf nodes.
- `weekly_downloads` is `-1` in many responses; PyPI BigQuery is the canonical source if needed.
- The `with_optional` graph picks up OS-specific clusters (e.g. `pyobjc-*`) and cloud-SDK clusters (`aws-cdk-*`, `azure-*`). These are kept rather than filtered; the heterogeneity is itself a property of the ecosystem.
- Betweenness on the 4,777-node graph takes ~1 to 2 minutes on CPU.
- Uses NetworkX's built-in `community.louvain_communities` (3.0+), not the older `python-louvain` package.

## License

MIT
