# Project 3 — Spark Benchmark
## Progress Tracker
*Last updated: 2026-04-21*

---

## Steps

### Phase 1 — Data generation + Pandas baseline
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | src/generate_data.py | ⬜ Todo | Generates synthetic Parquet at 1M / 10M / 100M rows. Without reproducible data at multiple scales the benchmark can't be run or compared across systems. Columns: timestamp, category, sensor_id, value, unit — representative of a sensor log or genomics metadata table. |
| 2 | src/pipeline_pandas.py | ⬜ Todo | Pandas implementation of the full pipeline (filter → broadcast join → aggregate → window). Single-node, in-memory, no cluster overhead — the baseline all other results are measured against. All other pipelines must produce identical output to this one (correctness gate). |
| 3 | Local baseline runs | ⬜ Todo | Run pipeline_pandas at 1M and 10M rows, record wall time and peak memory. 10M is where pandas starts to slow; 100M likely OOMs — which is exactly the motivation for Spark and GPU. |

### Phase 2 — Spark pipeline on UPPMAX
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 4 | src/pipeline_spark.py | ⬜ Todo | PySpark implementation of the same pipeline. Uses the DataFrame API and broadcast join hint for the small lookup table (avoids shuffle). Must produce identical aggregated output to pandas — confirmed before claiming any speedup. |
| 5 | jobs/uppmax_spark.sh | ⬜ Todo | SLURM submit script for UPPMAX. Module loading (Java, Spark), executor/memory flags, spark-submit invocation. Getting code to run on a cluster is a separate skill from writing the code — this is the HPC operations layer. |
| 6 | Results at 10M + 100M rows | ⬜ Todo | Run on UPPMAX, collect timing JSON per scale. These are the data points for benchmark_table.csv. 100M rows is where Spark's distribution overhead becomes worth paying vs. pandas. |
| 7 | Scaling experiment 1→4 nodes | ⬜ Todo | Run 100M rows at 1, 2, 4 executor nodes. Shows whether Spark scales linearly or where the bottleneck is (shuffle cost, driver overhead). The deviation from linear is the interesting story for Q8. |

### Phase 3 — GPU pipeline on Dardel
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 8 | src/pipeline_gpu.py | ⬜ Todo | cuDF implementation. API mirrors pandas so the diff is mostly `import cudf as pd`. GPU DataFrames are fast because columnar operations are vectorised on thousands of CUDA cores with HBM memory bandwidth — no Python GIL, no row iteration. |
| 9 | jobs/dardel_gpu.sh | ⬜ Todo | SLURM script for Dardel GPU partition (A100, 80 GB VRAM). `module load RAPIDS`, `--gres=gpu:a100:1`. 100M rows of this schema fits in 80 GB with room to spare — no chunking needed, which is cuDF's sweet spot. |
| 10 | Results at 10M + 100M rows | ⬜ Todo | Timing from Dardel. Single GPU vs single-node pandas at 100M rows is the headline comparison. Typically 5–20× faster on columnar filter/agg — the number goes into the Q8 narrative. |

### Phase 4 — Analysis + Docs
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 11 | results/benchmark_table.csv | ⬜ Todo | Consolidates all timing results: approach × scale × node_count → wall_time_s, throughput_rows_per_s, peak_memory_gb. The evidence base for all plots and the Q8 narrative — without it the comparison is anecdotal. |
| 12 | notebooks/benchmark_pipeline.ipynb | ⬜ Todo | Speedup curves (pandas = 1×), Spark scaling efficiency, cost-per-row chart. Visualising the crossover point makes the tradeoff concrete — "Spark is only worth it above X rows" is a much stronger claim with a chart. |
| 13 | docs/q8-hpc-narrative.md | ⬜ Todo | Written reflection: what UPPMAX/Dardel are, how SLURM works, why Spark shuffles are expensive, why cuDF is fast, where each wins. Grounded in the actual numbers from the benchmark runs — not theory. |

---

## Quick status

```
Phase 1  [░░░]  0/3  ← start here
Phase 2  [░░░░] 0/4
Phase 3  [░░░]  0/3
Phase 4  [░░░]  0/3
```
