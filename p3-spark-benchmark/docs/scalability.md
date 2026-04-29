# Scalability Analysis

## Data scaling strategy

Three scales chosen to expose qualitatively different regimes:

| Scale | Rows | Approx size (Parquet) | Expected behaviour |
|-------|------|-----------------------|--------------------|
| 1M  | 1,000,000  | ~170 MB | Pandas fast, Spark overhead dominates |
| 10M | 10,000,000 | ~1.7 GB | Pandas slowing, Spark break-even zone |
| 40M | 40,000,000 | ~6.8 GB | Pandas at memory limit, Spark and GPU win |

The full SRA archive (~40M RUN records) is used at the 40M scale — not a toy
dataset but the actual production catalog.

## Bottleneck by pipeline step

| Step | Pandas | Spark | GPU (cuDF) |
|------|--------|-------|------------|
| Filter | Memory copy | Partition scan (parallel) | HBM bandwidth |
| Broadcast join | In-memory merge | Broadcast serialisation | HBM copy |
| Aggregate | GroupBy hash table | **Shuffle** (network I/O) | Kernel launch |
| Window/cumsum | Sequential scan | Per-partition sequential | Sequential |

The shuffle in the aggregate step is Spark's dominant cost. Spark only wins
when data is too large for single-node RAM, or when shuffles can be minimised
(broadcast join avoids the lookup table shuffle entirely).

## Spark node scaling efficiency

Expected at 40M rows — ~80% efficiency due to shuffle and driver overhead:

```
Ideal:     1 node = T,  2 nodes = T/2,  4 nodes = T/4
Realistic: 1 node = T,  2 nodes = T/1.7,  4 nodes = T/3.2
```

Shuffle partitions set to `N_nodes × 40` in the SLURM script — standard
tuning heuristic. Too few → data skew on large partitions; too many →
scheduling overhead.

## GPU memory footprint

AMD MI250X has 128 GB HBM per GCD. At 40M rows:
- Raw Parquet: ~6.8 GB → ~12 GB in cuDF (decompressed, typed)
- After join: ~15 GB
- Well within 128 GB — no chunking needed

Multi-GPU required above ~300M rows for this schema.

## When to use what

```
Data fits in single-node RAM?
  Yes → Pandas (simplest, fastest iteration)
  No  → Spark multi-node

Workload is filter + aggregate (columnar)?
  Yes → GPU/cuDF fastest
  Complex window or large join → Spark or pandas

Need fast turnaround?
  GPU on Dardel if node available (minutes)
  Spark on UPPMAX adds ~10 min queue + startup overhead
```
