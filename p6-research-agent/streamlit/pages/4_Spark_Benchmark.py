import streamlit as st

st.set_page_config(page_title="Spark Benchmark", layout="wide")
st.title("📊 Spark Benchmark")
st.caption("Pandas vs PySpark vs cuDF (GPU) · NCBI SRA metadata · UPPMAX + Dardel HPC")

st.info("HPC jobs submitted to UPPMAX and Dardel. Results will appear here once collected.")

with st.sidebar:
    st.header("About")
    st.markdown("""
**Dataset:** NCBI SRA metadata — 1M to 40M rows of real genomics run records.

**Pipeline:** filter → broadcast join → aggregate → cumulative window

**Environments:**
- Pandas (local baseline)
- PySpark on UPPMAX Rackham (1/2/4 nodes)
- cuDF on Dardel GPU (AMD MI250X)

**Goal:** Measure where Spark's parallelism advantage over Pandas begins,
and how GPU acceleration compares at scale.
""")

st.markdown("""
### Local baseline (1M rows)

| Engine | Time | Throughput |
|--------|------|-----------|
| Pandas | 1.1 s | 0.94 M rows/s |
| Spark (1 node) | pending | — |
| cuDF (GPU) | pending | — |

### Speedup chart
*Will be populated after HPC runs complete.*
""")
