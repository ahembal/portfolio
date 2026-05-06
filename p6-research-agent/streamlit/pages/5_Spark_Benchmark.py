import streamlit as st

st.set_page_config(page_title="Spark Benchmark", layout="wide")
st.title("📊 Spark Benchmark")
st.caption("Pandas vs PySpark · NCBI SRA metadata · UPPMAX Pelle HPC")

st.success("Spark benchmark complete on UPPMAX Pelle (2026-05-05).")

with st.sidebar:
    st.header("About")
    st.markdown("""
**Dataset:** NCBI SRA metadata — real genomics sequencing run records from NCBI.

**Pipeline:** filter → broadcast join → aggregate → cumulative window

**This is an OLAP workload** — scanning large historical records, grouping,
aggregating, and computing trends over time. The standard pattern in data
engineering and research pipelines.

**Environments:**
- Pandas (local baseline, 1M rows)
- PySpark on UPPMAX Pelle (10M and 40M rows, 1/2/4 nodes)

**Question:** At what scale does distributed Spark outperform single-node Pandas?
""")

st.markdown("""
### Results

| Engine | Scale | Nodes | Time | Throughput |
|--------|-------|-------|------|-----------|
| Pandas | 1M | 1 | 1.1 s | 0.94 M rows/s |
| Spark | 10M | 1 | 5.6 s | 1.80 M rows/s |
| Spark | 10M | 2 | 5.3 s | 1.89 M rows/s |
| Spark | 10M | 4 | 5.7 s | 1.74 M rows/s |
| Spark | 40M | 1 | 7.0 s | 5.75 M rows/s |
| Spark | 40M | 2 | 6.7 s | 5.95 M rows/s |
| Spark | 40M | 4 | 7.5 s | 5.36 M rows/s |

### Key finding

Adding more nodes does not help at this scale — and sometimes makes it slightly
slower. At 10M and 40M rows the data fits comfortably in one node's memory.
The overhead of coordinating across nodes outweighs the parallelism benefit.

The crossover where distributed Spark adds value would likely be at 200M–400M
rows, or with heavier operations such as complex multi-table joins or ML
feature pipelines.

**The honest result:** distributed Spark is not always the right tool. For OLAP
pipelines at 1M–100M rows on a single node, Pandas or DuckDB are often faster
and simpler. Spark's strength is fault-tolerant processing at very large scale
where data does not fit on a single machine.
""")
