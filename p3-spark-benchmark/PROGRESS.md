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
| 1 | src/fetch_data.py | ✅ Done | Real NCBI SRA metadata (not synthetic) makes the benchmark reproducible and credible — the dataset has genuine quality issues (nulls, mixed platforms) that test pipeline robustness. NCBI SRA is updated daily and requires no authentication, making it reusable for future runs at larger scale. |
| 2 | src/pipeline_pandas.py | ✅ Done | Pandas establishes a single-threaded reference performance. Identical logic to the Spark and GPU pipelines means speedup measurements are apples-to-apples — any difference is attributable to the execution engine, not the query. |
| 3 | Local baseline runs | ✅ Done | The 1M baseline confirms the pipeline is correct before scaling to HPC. Load time dominating compute at 1M is expected — this is the crossover regime where Spark's parallelism overhead would make it slower, not faster. The baseline number anchors all future speedup calculations. |

### Phase 2 — Spark pipeline on UPPMAX
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 4 | src/pipeline_spark.py | ✅ Done | The broadcast join hint eliminates shuffle for the small platform_lookup table — it is the single highest-impact optimization. Shuffle partitions tuned per node count avoids over-partitioning at low node counts (scheduling overhead) and under-partitioning at high counts (stragglers). |
| 5 | jobs/uppmax_spark.sh | ✅ Done | Running 10M and 40M rows at 1/2/4 nodes in the same script gives the data for strong scaling curves (fixed problem size, more nodes) and shows the dataset size at which Spark's parallelism advantage over Pandas begins. |
| 6 | Results at 10M + 40M rows | ⬜ Todo | Submit to UPPMAX, collect timing JSONs. |
| 7 | Scaling experiment 1→4 nodes | ⬜ Todo | Already built into uppmax_spark.sh — runs automatically at each node count. |

### Phase 3 — GPU pipeline on Dardel
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 8 | src/pipeline_gpu.py | ✅ Done | cuDF on AMD MI250X (ROCm) matches the pandas and Spark query logic exactly — same correctness guarantee. The pandas fallback allows local testing without a GPU, so the code can be validated before the HPC job runs. |
| 9 | jobs/dardel_gpu.sh | ✅ Done | Dardel's MI250X GPUs are among the most powerful available on NAISS — this is the tier where GPU acceleration should show the largest speedup over Pandas and Spark. Running the same 10M/40M sizes as UPPMAX enables direct comparison across all three engines. |
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
