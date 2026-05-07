# P7 — RAG Evaluation & Hybrid Retrieval

## What and why

p6 builds a working research agent. p7 measures whether it works — and makes
it work better. These are distinct engineering problems. Building a RAG system
is straightforward; evaluating one without labelled data and improving retrieval
quality are the harder, more valuable challenges.

---

## Problem statement

A production RAG system answers thousands of questions. You cannot manually
check each answer. You need automated signals that tell you:

1. Is the retrieved content relevant to the question?
2. Is the generated answer faithful to the retrieved content?
3. Does the answer actually address what was asked?

Beyond evaluation: the current p6 agent retrieves the same way regardless of
query complexity. A simple factual question ("What gene encodes p53?") and a
complex multi-hop question ("Which proteins interact with TP53 and are also
implicated in DNA repair?") go through the same slow pipeline. This wastes
latency on simple queries and under-invests on complex ones.

---

## System components

### 1. Corpus population

Replaces the empty ChromaDB corpus in p6 with a real indexed knowledge base:
- Fetch PubMed abstracts for a defined set of life science topics
- Index at startup and refresh on a schedule
- Session indexing: papers retrieved via the agent are automatically added to
  the corpus for future queries

### 2. Hybrid search

Replaces pure dense vector search with a combination:
- **BM25** (lexical) — exact keyword matches, gene names, accession numbers
- **Dense vector** (semantic) — conceptual similarity
- **RRF fusion** (Reciprocal Rank Fusion) — combine both rankings into one

BM25 complements dense search on short queries and named entities (gene
symbols, drug names, PMIDs) where exact match matters more than semantic
similarity.

### 3. Cross-encoder reranker

After retrieval, a cross-encoder model scores each candidate passage against
the query. More accurate than bi-encoder similarity but too slow to run on
the full corpus — applied only to the top-20 candidates to produce top-5.

### 4. Adaptive retrieval

A lightweight query classifier routes queries to one of two paths:

- **Fast path** — simple factual questions, single-hop. Vector search only,
  no reranking. Target latency < 2s.
- **Slow path** — complex, multi-hop, comparative questions. Hybrid search +
  reranking + multi-step agent. Target latency 30–60s.

The classifier is a small model (or rule-based heuristic) that predicts query
complexity before retrieval starts.

### 5. Evaluation pipeline (LLM-as-judge)

Automated scoring without labelled data, inspired by RAGAS:

| Metric | What it measures | How |
|--------|-----------------|-----|
| Context relevance | Are retrieved chunks relevant to the question? | LLM scores each chunk |
| Faithfulness | Does the answer contain only claims supported by retrieved content? | LLM checks each claim |
| Answer relevance | Does the answer address the question asked? | LLM scores the response |

Scores are computed per query and aggregated. Run on a fixed benchmark set
to track improvement across system changes.

### 6. Benchmark dataset

50 curated life science questions with:
- The question
- Expected answer type (factual / comparative / multi-hop)
- Ground-truth PMIDs that should be retrieved
- Reference answer (for faithfulness scoring)

Questions are sourced from PubMed and manually verified. The benchmark is
versioned and fixed — results are reproducible.

---

## What this builds on

- p6 `src/tools/vector_store.py` — extended with BM25 and RRF fusion
- p6 `src/agent/graph.py` — extended with fast/slow routing
- p6 `src/tools/pubmed.py` — corpus population uses the same Entrez client
- p6 ChromaDB PVC — same storage, larger corpus

---

## Out of scope

- Full re-implementation of p6 — p7 extends, does not replace
- Training a new embedding model from scratch
- Serving at production scale (millions of queries)
- GPU inference for the reranker (CPU is sufficient for demo)
