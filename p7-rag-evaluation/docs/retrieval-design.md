# Retrieval Architecture
*p7 — RAG Evaluation & Hybrid Retrieval*

---

## Why hybrid retrieval

Two retrieval methods dominate the literature:

**BM25 (sparse)** — scores documents by term frequency weighted by inverse
document frequency. Exact vocabulary match. Fast, no model required, excels on
queries with rare or specific terms (gene names, accession numbers, drug names).

**Dense vector search (semantic)** — encodes query and documents into embeddings,
retrieves by cosine similarity. Finds semantically related content even when
vocabulary doesn't overlap. Better for conceptual or paraphrased queries.

Neither is strictly better:

| Query type | BM25 | Dense |
|------------|------|-------|
| "TP53 P04637 glioblastoma" | ✅ exact terms | ❌ may miss rare tokens |
| "What causes brain tumours" | ❌ vocabulary mismatch | ✅ semantic match |
| "Compare BRCA1 and BRCA2" | ❌ both terms are common | ✅ contextual |
| Rare disease names | ✅ | ❌ OOV or low-frequency |

Hybrid retrieval combines both, fusing their results before reranking. For the
life science domain — where queries mix technical identifiers with natural language
— this is the correct default.

---

## The retrieval pipeline

```
Query
  │
  ├─ Classifier ──────────────────────────┐
  │   (simple / complex)                  │
  │                                       │
  │  Simple path (fast)            Complex path (slow)
  │  Dense search only             BM25 + Dense → RRF → Reranker
  │  top-5 results                 top-5 from top-20 fused results
  │                                       │
  └───────────────────────────────────────┘
                    │
                   Results
```

---

## BM25 — sparse retrieval

**Implementation:** `rank-bm25` library. Corpus is tokenised and indexed at startup.
BM25 scores are computed against the query tokens at query time.

**Formula:**

```
BM25(q, d) = Σ IDF(t) × (tf(t,d) × (k1 + 1)) / (tf(t,d) + k1 × (1 - b + b × |d|/avgdl))
```

Where:
- `tf(t,d)` — term frequency of token t in document d
- `IDF(t)` — inverse document frequency: log((N - df + 0.5) / (df + 0.5))
- `k1 = 1.5` — term frequency saturation parameter
- `b = 0.75` — document length normalisation parameter
- `|d|/avgdl` — document length relative to corpus average

The key intuition: IDF down-weights terms that appear in many documents ("the",
"protein") and up-weights terms that are rare and discriminative ("glioblastoma",
"P04637"). k1 controls how much term frequency beyond the first occurrence matters.

**Limitations for life science text:**
- Synonyms are not matched ("TP53" ≠ "p53" ≠ "tumour suppressor" in BM25)
- Multi-word entity names require exact tokenisation ("epidermal growth factor
  receptor" vs "EGFR")
- Stemming can hurt for gene names (stemming "KRAS" may lose the exact match)

---

## Dense vector search — semantic retrieval

**Implementation:** `sentence-transformers` with `all-MiniLM-L6-v2`, indexed in
ChromaDB. Documents are encoded once at ingestion; queries are encoded at runtime.

**Why all-MiniLM-L6-v2:**
90 MB model, runs on CPU without a GPU, produces 384-dimensional embeddings.
At the scale of the p7 corpus (PubMed abstracts), retrieval quality is sufficient
for the hybrid pipeline where BM25 handles the vocabulary-match cases.

A larger model (`all-mpnet-base-v2`, 420 MB) produces better embeddings but uses
~4× more memory and is slower on CPU. The marginal quality gain does not justify
the resource cost for a CPU-only deployment.

**Limitations:**
- Embeddings are fixed at index time — a new model requires re-indexing the corpus
- Semantic similarity is not the same as factual relevance. A document about
  "TP53 in zebrafish" is semantically similar to "TP53 in human cancer" but may
  not be relevant.
- Dense models struggle on rare entities not seen during pretraining

---

## Reciprocal Rank Fusion (RRF)

After BM25 and dense retrieval each return a ranked list of 20 candidates, the
two lists are merged using RRF:

```
RRF(d) = Σ 1 / (k + rank_i(d))
```

Where `rank_i(d)` is the rank of document d in list i, and k=60 is a constant
that reduces the impact of very high ranks.

**Why RRF instead of score normalisation:**
BM25 scores and cosine similarities are on different scales and cannot be directly
averaged. Normalising to [0,1] requires knowing the score distribution in advance.
RRF uses only rank positions, not raw scores — it is robust to distribution
differences and consistently outperforms score normalisation in empirical benchmarks.

**Example:**

| Document | BM25 rank | Dense rank | RRF score |
|----------|-----------|------------|-----------|
| A | 1 | 3 | 1/61 + 1/63 = 0.0321 |
| B | 5 | 1 | 1/65 + 1/61 = 0.0318 |
| C | 2 | 8 | 1/62 + 1/68 = 0.0309 |

Document A ranks first in BM25 and third in dense — RRF gives it the highest
combined score. A document that ranks well in both systems consistently gets
promoted to the top of the fused list.

---

## Cross-encoder reranking

The top-20 fused candidates are passed to a cross-encoder for reranking. The
cross-encoder reads both the query and each candidate simultaneously, computing
a relevance score that accounts for their full interaction — unlike the bi-encoder
used for dense retrieval, which encodes query and document independently.

**Why not rank with the bi-encoder:**
A bi-encoder must encode documents at index time (no query context). The resulting
embeddings capture "what this document is about" but not "how relevant this
document is to this specific query." A cross-encoder reads both at once, capturing
fine-grained relevance signals that the bi-encoder misses.

**The cost:** Cross-encoders are slow — they run inference for every candidate
on every query. At 20 candidates and ~100ms per inference, that's 2 seconds per
query. This is why cross-encoding is applied only to the top-20 pre-filtered
candidates rather than the full corpus.

**The adaptive routing trade-off:**

| Path | Cost | When used |
|------|------|----------|
| Fast (dense only) | ~200ms | Simple factual queries |
| Slow (BM25 + dense + RRF + reranker) | ~2-3s | Complex multi-concept queries |

The classifier (a lightweight rule-based model) routes queries to the appropriate
path. The cost savings on simple queries (which constitute the majority of traffic)
pay for the higher quality on complex queries.

---

## Query classification

The classifier uses heuristic features to route queries:

**Simple indicators:** short query (< 6 tokens), single entity, factual
("what is", "define", "what does X stand for")

**Complex indicators:** comparison operators ("vs", "compare", "differ"),
multiple entities, causal questions ("how does", "why does", "mechanism"),
temporal or conditional structure

This is intentionally simple — a more sophisticated classifier would require
labelled training data and would introduce its own failure modes. The heuristic
covers the dominant cases correctly.

**What happens on misclassification:**
- Simple query sent to slow path: correct result, 10× slower, not a problem
- Complex query sent to fast path: potentially incomplete result, much faster

The classifier is biased toward the slow path for borderline cases — the
quality cost of under-retrieving is higher than the latency cost of over-computing.

---

## Corpus and ingestion

The corpus is PubMed abstracts fetched via the PubMed E-utilities API, stored
in ChromaDB as 512-character chunks with 64-character overlap. The overlap
ensures entity mentions at chunk boundaries are not split.

**Why chunk abstracts rather than index whole abstracts:**
A 250-word abstract embedded as one vector may score well for the topic but
poorly for a specific claim buried in the third sentence. Chunking allows the
retriever to surface the specific passage relevant to the query, not just the
abstract as a whole.

**Chunk size trade-off:**
512 characters (~80-100 words) captures enough context to make a claim
self-contained while remaining small enough that the embedding is specific.
Larger chunks (1024+) dilute the embedding; smaller chunks (256) lose context
for technical claims that span multiple sentences.
