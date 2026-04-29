# Project 3 — Spark Benchmark
## Progress Tracker
*Last updated: 2026-04-28*

---

## Cluster constraints
> See `runbooks/known-issues.md` for full details.
- **Actual benchmarks run on HPC (UPPMAX/Dardel via SLURM)** — not on the homelab cluster
- Homelab cluster only used for: results dashboard / notebook server if added
- If K8s deployment is added: schedule on `quick-thrush`, copy `ghcr-pull-secret` to namespace
- `sought-perch` is cordoned — do not schedule there (ISS-009)

---

## Steps

### Phase 1 — Data generation + Pandas baseline
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | src/fetch_data.py | ✅ Done | Streams real NCBI SRA metadata (not synthetic). ~40M RUN records, updated daily. No auth needed. Fetches 1M rows in ~3 min locally; larger scales staged on HPC. See docs/data-source.md for schema, fetch timing, and data quality notes. |
| 2 | src/pipeline_pandas.py | ✅ Done | Pandas baseline: filter (live + Bases>0) → broadcast join with platform_lookup → aggregate (Center/technology/year) → cumulative window. Writes Parquet + timing JSON. |
| 3 | Local baseline runs | ✅ Done | 1M rows: 1.1s, 0.94 M rows/s. Load=0.55s dominates. Compute (filter+join+agg+window)=0.51s. Results in results/pandas_sra_runs_1M.json. |

### Phase 2 — Spark pipeline on UPPMAX
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 4 | src/pipeline_spark.py | ✅ Done | PySpark version. Broadcast join hint, shuffle partitions tuned per node count. Identical logic to pandas — correctness verified by output diff. |
| 5 | jobs/uppmax_spark.sh | ✅ Done | SLURM script for Rackham. Account naiss2026-4-384, 4 nodes, runs 10M + 40M at 1/2/4 nodes. |
| 6 | Results at 10M + 40M rows | ⬜ Todo | Submit to UPPMAX, collect timing JSONs. |
| 7 | Scaling experiment 1→4 nodes | ⬜ Todo | Already built into uppmax_spark.sh — runs automatically at each node count. |

### Phase 3 — GPU pipeline on Dardel
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 8 | src/pipeline_gpu.py | ✅ Done | cuDF version with ROCm backend (Dardel uses AMD MI250X, not NVIDIA). Falls back to pandas if cuDF unavailable (for local testing). |
| 9 | jobs/dardel_gpu.sh | ✅ Done | SLURM script for Dardel GPU. Account naiss2026-4-384, MI250X, module load RAPIDS/24.06-rocm-6.0. Runs 10M + 40M rows. |
| 10 | Results at 10M + 40M rows | ⬜ Todo | Submit to Dardel, collect timing JSONs. |

### Phase 4 — Analysis + Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 11 | results/benchmark_table.csv | ⬜ Todo | Consolidate all timing JSONs after HPC runs complete. |
| 12 | notebooks/benchmark_pipeline.ipynb | ⬜ Todo | Speedup plots and crossover analysis. Written after results are in. |
| 13 | docs/q8-hpc-narrative.md | ⬜ Todo | Skeleton exists. Fill in with real numbers after HPC runs. |

---

## Quick status

```
Phase 1  [███]  3/3  ✅ Done
Phase 2  [██░░] 2/4  ← submit to UPPMAX
Phase 3  [██░]  2/3  ← submit to Dardel
Phase 4  [░░░]  0/3  ← after HPC results
```
