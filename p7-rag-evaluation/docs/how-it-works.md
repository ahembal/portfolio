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

**Input:**
```python
bm25.search("BRCA1 mutation breast cancer", k=3)
```

**Output:**
```python
[
  {"text": "BRCA1 mutation increases breast cancer risk...", "source": "pubmed:123", "score": 4.21, "rank": 1},
  {"text": "Breast cancer treatment with chemotherapy...",   "source": "pubmed:456", "score": 2.10, "rank": 2},
  {"text": "DNA damage repair in tumour suppression...",     "source": "pubmed:789", "score": 0.0,  "rank": 3},
]
```

**Weakness:** the DNA repair doc scores 0 even though BRCA1 is a DNA repair gene
— the exact words don't appear. Dense search fills this gap.

---

## Dense vector search — semantic search

A sentence-transformer encodes the query and each document chunk into a
high-dimensional vector. Chunks whose meaning is close to the query have vectors
close in that space.

**Input:**
```python
vector_store.search("BRCA1 breast cancer DNA repair", k=3)
```

**Output:**
```python
[
  {"text": "DNA damage repair in tumour suppression...", "source": "pubmed:789", "score": 0.91, "rank": 1},
  {"text": "BRCA1 mutation increases breast cancer...",  "source": "pubmed:123", "score": 0.87, "rank": 2},
  {"text": "Breast cancer treatment with chemo...",      "source": "pubmed:456", "score": 0.74, "rank": 3},
]
```

**Weakness:** exact identifiers like `P04637` may not be close to anything in
the embedding space. The model has never seen that accession in meaningful context.

---

## Hybrid search — combining both

Each method produces an independent ranked list. RRF (Reciprocal Rank Fusion)
merges them into one:

```
Query: "BRCA1 breast cancer DNA repair"

BM25 ranking:          Dense ranking:
1. pubmed:123          1. pubmed:789   ← semantic match (DNA repair)
2. pubmed:456          2. pubmed:123   ← also a semantic match
3. pubmed:789          3. pubmed:456

RRF score = Σ  1 / (k + rank)   where k=60 (standard constant)

pubmed:123:  1/(60+1) + 1/(60+2)  = 0.0164 + 0.0161 = 0.0325  ← ranked 1st
pubmed:789:  1/(60+3) + 1/(60+1)  = 0.0159 + 0.0164 = 0.0323  ← ranked 2nd
pubmed:456:  1/(60+2) + 1/(60+3)  = 0.0161 + 0.0159 = 0.0320  ← ranked 3rd
```

**Input:**
```python
fused = rrf.fuse(bm25_results, dense_results)
```

**Output:**
```python
[
  {"text": "BRCA1 mutation increases breast cancer...", "source": "pubmed:123", "rrf_score": 0.0325},
  {"text": "DNA damage repair in tumour suppression..","source": "pubmed:789", "rrf_score": 0.0323},
  {"text": "Breast cancer treatment with chemo...",    "source": "pubmed:456", "rrf_score": 0.0320},
]
```

---

## Cross-encoder reranking

BM25 and dense search embed the query and document separately. A cross-encoder
reads them *together*, which lets it model their interaction directly:

```
Input:  "BRCA1 breast cancer" [SEP] "BRCA1 mutation increases breast cancer risk..."
Output: 9.4   ← raw relevance logit (higher = more relevant)

Input:  "BRCA1 breast cancer" [SEP] "Breast cancer treatment with chemotherapy..."
Output: 2.1
```

Applied only to the top-20 candidates from hybrid search — never the full corpus.

**Input:**
```python
rerank("BRCA1 breast cancer", fused_results, top_n=5)
```

**Output:**
```python
[
  {"text": "BRCA1 mutation increases breast cancer...", "source": "pubmed:123", "rrf_score": 0.0325, "rerank_score": 9.4},
  {"text": "DNA damage repair in tumour suppression..","source": "pubmed:789", "rrf_score": 0.0323, "rerank_score": 7.1},
  ...
]
```

**Two-stage pipeline:**
```
Full corpus (thousands of chunks)
        │
        ▼
  Hybrid search (BM25 + dense + RRF)   ← fast, retrieves top-20
        │
        ▼
  Cross-encoder reranker               ← accurate, scores top-20
        │
        ▼
  Top-5 results passed to LLM
```

---

## Adaptive retrieval

Not all queries need the full pipeline. A factual single-hop question has one
answer dense search finds instantly — routing it through hybrid + reranking
adds latency with no quality gain.

```
Query
  │
  ▼
┌─────────────────────────┐
│  Complexity classifier   │
│                          │
│  simple  → fast path     │──► vector search only        < 2s
│  complex → slow path     │──► hybrid + rerank           30–60s
└─────────────────────────┘
```

**Input / output:**
```python
retrieve("What is EGFR?")
# → {"results": [...], "path": "fast", "query": "What is EGFR?"}

retrieve("How does EGFR signalling interact with mTOR in lung cancer?")
# → {"results": [...], "path": "slow", "query": "..."}
```

**Simple queries** (fast path): factual lookups, named entity questions, single expected answer.

**Complex queries** (slow path): comparative, mechanistic, multi-hop, multi-entity.

---

## LLM-as-judge evaluation

The judge LLM is called three times per query — once per metric. Each call
receives a structured prompt and must return a JSON object.

**Context relevance** — are the retrieved chunks relevant to the question?

```
Prompt:  "How many of the 3 passages are relevant to: 'How does TP53 regulate apoptosis?'"
         [passage 1] ... [passage 2] ... [passage 3] ...
         Reply with only: {"relevant": <int>, "total": 3}

Response: {"relevant": 2, "total": 3}
Score:    2/3 = 0.667
```

**Faithfulness** — does the answer contain only claims from the chunks?

```
Prompt:  "List each factual claim in the answer. Is each supported by the passages?"
         Answer: "TP53 activates BAX to trigger apoptosis."
         Reply with only: {"supported": <int>, "total": <int>}

Response: {"supported": 1, "total": 1}
Score:    1/1 = 1.0
```

**Answer relevance** — does the answer address what was asked?

```
Prompt:  "Score 0.0–1.0 how well this answer addresses the question."
         Question: "How does TP53 regulate apoptosis?"
         Answer: "TP53 activates pro-apoptotic genes such as BAX..."
         Reply with only: {"score": <float>}

Response: {"score": 0.9}
Score:    0.9
```

**Full evaluation output:**
```python
evaluate(query, chunks, answer, llm)
# →
{
  "context_relevance": 0.667,
  "faithfulness":      1.0,
  "answer_relevance":  0.9,
}
```

**Aggregate across benchmark:**
```python
{
  "context_relevance": 0.71,
  "faithfulness":      0.84,
  "answer_relevance":  0.78,
  "n_queries":         20,
  "fast_path_pct":     45.0,
}
```

**Limitation:** the judge LLM can be wrong. A faithfulness score of 0.84 means
the judge thinks 84% of claims are grounded — not that they actually are.
This is a signal, not ground truth. See `docs/evaluation-design.md` for a full
discussion of what automated evaluation can and cannot measure.
