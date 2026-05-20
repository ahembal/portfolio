# Design Decisions
*p6 — Research Agent*

---

## Resource sizing — research-agent-api

**Decision:** `memory: limit 8Gi, request 1Gi` / `cpu: limit 2, request 250m`

**Why:**

The API has two distinct memory profiles depending on what it is doing:

| Mode | Memory usage |
|------|-------------|
| Idle / serving RAG queries | ~1GB — model loaded, one query at a time |
| Corpus ingestion (bulk embedding) | ~2–3GB peak — sentence-transformer encoding hundreds of documents |

The initial limit of `1Gi` was set conservatively at deploy time before the
ingestion workload was known. It caused OOMKill (exit code 137) during ingestion.

**Sizing rationale for 8Gi:**

| Component | Memory |
|-----------|--------|
| Python app + FastAPI | ~200MB |
| Sentence-transformer model (all-MiniLM-L6-v2) | ~500MB |
| ChromaDB client | ~100MB |
| Embedding batch peak (200 docs) | ~2–3GB |
| Safety margin (2×) | — |
| **Total** | ~4GB needed → 8Gi limit |

quick-thrush has 64GB RAM. Ollama already reserves 20GB. 8Gi for the API
is not wasteful and leaves >30GB free for other workloads.

The request is kept at `1Gi` so Kubernetes schedules the pod normally — the
higher limit only kicks in during ingestion spikes.

---

## Sentence-transformer model choice

**Decision:** `all-MiniLM-L6-v2` (default in sentence-transformers)

A balance between quality and resource use. At 90MB and ~500MB runtime memory,
it runs comfortably on CPU. Larger models (e.g. `all-mpnet-base-v2`) produce
better embeddings but use significantly more memory and are slower on CPU.

For a homelab demo querying PubMed abstracts, `all-MiniLM-L6-v2` is sufficient.
A production system with stricter retrieval quality requirements would use a
larger model or a GPU-backed embedding service.

---

## ChromaDB as vector store

**Decision:** ChromaDB persistent client on a ceph-rbd PVC (5Gi)

ChromaDB was chosen over alternatives (Pinecone, Weaviate, Qdrant) because it
runs locally with no external service dependency and integrates with
sentence-transformers directly. For a homelab portfolio project where simplicity
and self-containment matter, it is the right choice.

The PVC ensures the indexed corpus survives pod restarts — rebuilding embeddings
for the full corpus takes several minutes and would be wasteful on every restart.
