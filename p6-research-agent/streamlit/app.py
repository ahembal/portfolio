import streamlit as st

st.set_page_config(page_title="ML Portfolio", page_icon="🧬", layout="wide")

st.title("ML Engineering Portfolio")
st.caption("Emre Balsever · Life Science ML · K8s · GitOps · LLM Agents")

st.markdown("""
Select a project from the sidebar to explore a live demo.

---

### Projects

| | Project | What it does |
|-|---------|-------------|
| 🔬 | **PCam Classifier** | Upload a histology patch → tumour / normal prediction |
| 📦 | **Metadata Ingestion** | Upload a file → async pipeline → Postgres + S3 |
| 🧬 | **Research Agent** | Ask a life science question → LLM agent with PubMed + UniProt |
| 📊 | **Spark Benchmark** | Pandas vs Spark vs GPU at scale on HPC |

---

### Shared infrastructure

All live services run on a 3-node homelab Kubernetes cluster managed via
ArgoCD GitOps. Each project has its own Helm chart, CI/CD pipeline, and
deployment troubleshooting log.

→ See [BIGPICTURE.md](https://github.com/ahembal/portfolio/blob/main/BIGPICTURE.md)
for the full portfolio map.
""")
