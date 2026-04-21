# P3 — Spark Benchmark — Spec

> Last updated: 2026-04-21

## What this project is

A benchmark comparing three processing approaches on the same ETL pipeline:

1. **Pandas** — single-node in-memory baseline (what everyone starts with)
2. **PySpark** — distributed processing on UPPMAX (NAISS HPC cluster) via SLURM
3. **GPU / cuDF** — GPU-accelerated DataFrames on PDC Dardel (NVIDIA A100) via SLURM

Same pipeline logic, same dataset, three runtimes. The goal is to measure where each approach
wins, at what data scale the crossover happens, and what the operational cost of each is.

**Portfolio question answered:** Q8 — HPC narrative: real hands-on experience with UPPMAX and
Dardel, SLURM job submission, distributed Spark, GPU computing.

---

## Dataset

Synthetic tabular Parquet dataset — mimics a sensor log or genomics metadata table.
Synthetic means no data transfer headaches while still exercising realistic patterns.
Generated at multiple scales: 1M rows (~200 MB), 10M rows (~2 GB), 100M rows (~20 GB).

---

## Benchmark pipeline (identical logic in all three)

```
Input: Parquet files (partitioned by date)
  ├── Filter        rows where value < threshold (selective scan)
  ├── Broadcast join  enrich with a small lookup table
  ├── Aggregate     group by (category, date) → mean, stddev, count
  ├── Window        rolling 7-day mean per category
  └── Output        Parquet + summary stats JSON (wall time, throughput)
```

Filter → join → aggregate → window covers the main cost patterns in ETL:
I/O, shuffle, memory pressure, and sequential dependency.

---

## Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Pandas | pandas 2.x + pyarrow | Baseline. Fast for small data, hits RAM wall at scale |
| Spark | PySpark 3.5 | Distributed across UPPMAX nodes; partition-parallel |
| GPU | cuDF (RAPIDS 24.x) | GPU DataFrame API mirrors pandas; A100 has 80 GB HBM |
| Scheduler | SLURM | Standard on both UPPMAX and Dardel |
| Results | CSV + notebook | benchmark_table.csv + benchmark_pipeline.ipynb |

---

## Critical path

```
generate synthetic data (1M / 10M / 100M rows)
  → pandas pipeline (local, fast)
    → spark pipeline on UPPMAX (SLURM job)
      → GPU pipeline on Dardel (SLURM job)
        → consolidate results → benchmark_table.csv
          → analysis notebook (speedup plots)
            → Q8 doc
```

---

## Phase 1 — Data generation + Pandas baseline

| # | Task | Why |
|---|------|-----|
| 1 | `src/generate_data.py` | Creates synthetic Parquet at configurable scale. Without this, can't run or reproduce the benchmark. Columns: timestamp, category, sensor_id, value, unit. |
| 2 | `src/pipeline_pandas.py` | The baseline. Runs the full filter→join→agg→window pipeline in pandas. Records wall time via `time.perf_counter()` and writes `results/pandas_{scale}.json`. |
| 3 | Run locally at 1M + 10M rows | Establishes the baseline numbers. 10M rows is where pandas starts to slow; 100M rows likely OOMs on a laptop. |

**Done when:** `python src/pipeline_pandas.py --scale 1M` completes, output Parquet matches expected row count, timing JSON written.

---

## Phase 2 — Spark pipeline on UPPMAX

| # | Task | Why |
|---|------|-----|
| 4 | `src/pipeline_spark.py` | PySpark version of the same pipeline. Uses `spark.read.parquet`, DataFrame API (not RDD), broadcast join hint for the lookup table. Must produce identical output to pandas (correctness gate). |
| 5 | `jobs/uppmax_spark.sh` | SLURM submit script. Specifies: `#SBATCH --account`, `--nodes`, `--ntasks-per-node`, `module load java spark`. Calls `spark-submit` with executor memory and core flags tuned for UPPMAX node spec. |
| 6 | Submit + collect results | Run at 10M and 100M rows. Multiple node counts (1, 2, 4) to show scaling. Results → `results/spark_{scale}_{nodes}nodes.json`. |
| 7 | Scaling experiment | Compare 1-node vs 4-node Spark at 100M rows. Shows near-linear speedup (or explains why it isn't). |

**Done when:** SLURM job exits 0; results present; output Parquet matches pandas output (diff check on aggregated values).

---

## Phase 3 — GPU pipeline on Dardel

| # | Task | Why |
|---|------|-----|
| 8 | `src/pipeline_gpu.py` | cuDF version. cuDF mirrors the pandas API so the diff is mostly `import cudf as pd`. Key differences: GPU memory management (`rmm`), no rolling window in cuDF (fall back to custom kernel or skip). |
| 9 | `jobs/dardel_gpu.sh` | SLURM script for Dardel GPU partition. `#SBATCH -p gpu`, `--gres=gpu:a100:1`, `module load RAPIDS`. cuDF requires the data to fit in GPU VRAM (80 GB on A100 — fine for 100M rows of this schema). |
| 10 | Submit + collect results | Run at 10M and 100M rows. Single GPU is the meaningful comparison point against single-node pandas and 1-node Spark. |

**Done when:** Dardel job exits 0; timing results present; output matches pandas reference.

---

## Phase 4 — Analysis + Docs

| # | Task | Why |
|---|------|-----|
| 11 | `results/benchmark_table.csv` | Consolidated: approach × scale × nodes → wall_time_s, throughput_rows_per_s, peak_memory_gb. Single source of truth for all plots. |
| 12 | `notebooks/benchmark_pipeline.ipynb` | Speedup curves (pandas baseline = 1x), scaling efficiency plot for Spark, cost-per-row comparison. Matplotlib/seaborn. |
| 13 | `docs/q8-hpc-narrative.md` | Written reflection: what UPPMAX and Dardel are, how SLURM works, Spark shuffle cost, cuDF memory model, when to use each approach, honest account of HPC friction (module conflicts, queue wait times, job preemption). |

---

## Acceptance criteria (project complete)

- [ ] All three pipelines produce identical aggregated output (correctness verified)
- [ ] `benchmark_table.csv` has ≥ 6 data points (3 approaches × 2 scales minimum)
- [ ] Notebook with speedup plots committed and renders cleanly
- [ ] `docs/q8-hpc-narrative.md` written with concrete numbers from the actual runs
