# How It Works
*p7 — RAG Evaluation & Hybrid Retrieval*

---

## The problem with pure vector search

A dense vector search encodes meaning. Given the query "TP53 glioblastoma", it
finds documents about p53, tumour suppressors, and brain cancer — even if those
exact words don't appear. This is powerful for conceptual questions.

But it fails on exact identifiers:

- Gene symbol `BRCA1` — semantically similar to many genes, exact match matters
- Accession `P04637` — no semantic meaning at all
- Drug name `Temozolomide` — exact spelling is the signal

For these, a search that looks for the exact string outperforms one that looks
for meaning. This is where BM25 comes in.

---

## BM25 — lexical search

BM25 (Best Match 25) scores documents by how well they match the query terms
exactly. The score is higher when:

- The query term appears frequently in the document
- The document is short (a term appearing 3 times in a 50-word abstract is more
  relevant than the same term in a 5000-word review)

```
Query: "BRCA1 mutation breast cancer"

Corpus:
  doc_A: "BRCA1 mutation increases breast cancer risk significantly"  → high score
  doc_B: "Breast cancer treatment with chemotherapy"                  → medium (2 terms)
  doc_C: "DNA damage repair mechanisms in tumour suppression"         → low (0 exact terms)
```

**Weakness:** doc_C may be highly relevant (BRCA1 is a DNA repair gene) but
scores zero because the exact words don't appear.

---

## Dense vector search — semantic search

A sentence-transformer encodes the query and each document chunk into a
high-dimensional vector. Chunks whose meaning is close to the query have vectors
close in that space.

```
Query embedding:    [0.12, -0.34, 0.87, ...]
doc_A embedding:    [0.11, -0.31, 0.85, ...]  ← close → high similarity
doc_C embedding:    [0.09, -0.28, 0.79, ...]  ← also close (DNA repair ≈ BRCA1)
doc_D embedding:    [0.91,  0.44, -0.12, ...]  ← far → low similarity
```

**Weakness:** exact identifiers like `P04637` may not be close to anything in
the training data. The model has never seen that accession number used in
meaningful context.

---

## Hybrid search — combining both

Each method produces an independent ranked list. RRF (Reciprocal Rank Fusion)
merges them:

```
Query: "BRCA1 breast cancer DNA repair"

BM25 ranking:          Dense ranking:
1. doc_A               1. doc_C   ← semantic match (DNA repair)
2. doc_B               2. doc_A   ← also a semantic match
3. doc_E               3. doc_B

RRF score = Σ  1 / (k + rank)   where k=60 (standard constant)

doc_A:  1/(60+1) + 1/(60+2)  = 0.0164 + 0.0161 = 0.0325  ← ranked 1st
doc_C:  0        + 1/(60+1)  = 0      + 0.0164 = 0.0164  ← ranked 2nd
doc_B:  1/(60+2) + 1/(60+3)  = 0.0161 + 0.0159 = 0.0320  ← ranked 3rd
```

A document ranked high in both lists gets the strongest combined score.
RRF requires no tuning — the k=60 constant works well across domains.

---

## Cross-encoder reranking

BM25 and dense search both use independent encodings — the query and document
are embedded separately and compared. This is fast but imprecise.

A cross-encoder reads the query and document *together* as one input, which
lets it model the interaction between them directly:

```
Input:  [query] SEP [document chunk]
Output: relevance score 0–1
```

This is more accurate but slow — running a cross-encoder on 10,000 chunks
for every query would take minutes. The solution is a two-stage pipeline:

```
Full corpus (thousands of chunks)
        │
        ▼
  Hybrid search (BM25 + dense + RRF)
        │  fast, retrieves top-20 candidates
        ▼
  Cross-encoder reranker
        │  slow but accurate, scores top-20
        ▼
  Top-5 results passed to LLM
```

The reranker only ever sees 20 candidates — fast enough for real-time use.

---

## Adaptive retrieval

Not all queries need the full pipeline. A factual single-hop question
("What gene encodes p53?") has one answer that dense search finds instantly.
Routing it through hybrid search + reranking adds latency with no quality gain.

A query complexity classifier routes queries before retrieval starts:

```
Query
  │
  ▼
┌─────────────────────────┐
│  Complexity classifier   │
│                          │
│  simple  → fast path     │──► vector search only        < 2s
│  complex → slow path     │──► hybrid + rerank + agent  30–60s
└─────────────────────────┘
```

**Simple queries** (fast path):
- Single factual question
- Named entity lookup ("what is EGFR?")
- One expected answer

**Complex queries** (slow path):
- Comparative ("compare BRCA1 and BRCA2 roles in DNA repair")
- Multi-hop ("which proteins interact with TP53 and are implicated in GBM?")
- Mechanistic ("how does p53 regulate apoptosis?")

---

## LLM-as-judge evaluation

Evaluating RAG without labelled data uses an LLM to score three properties
of each query-retrieval-answer triple:

```
Query ──────────────────────────────────────────────────────┐
                                                            │
Retrieved chunks ───────────────────────────────────────┐  │
                                                         │  │
Generated answer ────────────────────────────────────┐  │  │
                                                      │  │  │
                                                      ▼  ▼  ▼
                                               ┌─────────────────┐
                                               │   LLM judge      │
                                               │                  │
                                               │ Context          │
                                               │ relevance ───────► 0–1
                                               │                  │
                                               │ Faithfulness ────► 0–1
                                               │                  │
                                               │ Answer           │
                                               │ relevance ───────► 0–1
                                               └─────────────────┘
```

| Metric | Question asked to the judge |
|--------|-----------------------------|
| Context relevance | Are the retrieved chunks relevant to the query? |
| Faithfulness | Does the answer contain only claims supported by the chunks? |
| Answer relevance | Does the answer address what was asked? |

Scores are computed per query and aggregated across the benchmark to produce
system-level metrics. Running the same benchmark before and after a retrieval
change shows whether quality improved.

**Limitation:** the judge LLM can be wrong. A faithfulness score of 0.85 means
the judge thinks 85% of claims are grounded — not that they actually are.
This is a signal, not ground truth. See `docs/evaluation-design.md` for a full
discussion of what automated evaluation can and cannot measure.
