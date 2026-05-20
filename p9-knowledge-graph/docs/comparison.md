# RAG vs SPARQL — When to Use Which
*p9 — Knowledge Graph & Semantic Search*

---

## The core difference

RAG and SPARQL answer different kinds of questions. Using the wrong tool for
the question type produces either wrong answers (RAG on structured queries) or
rigid responses (SPARQL on open-ended questions).

| Dimension | RAG (p6/p7) | SPARQL (p9) |
|-----------|-------------|-------------|
| Data representation | Unstructured text chunks in a vector store | Explicit triples in a knowledge graph |
| Query mechanism | Semantic similarity — finds text *about* the topic | Pattern matching — finds exact stated facts |
| Strengths | Open-ended synthesis, analogical reasoning, summarisation | Precise set operations, multi-hop traversal, aggregation |
| Weaknesses | Cannot count reliably, hallucinates relationships | Cannot synthesise or explain, requires structured data |
| Answers are | Grounded in retrieved passages — may be imprecise | Exact — either the fact is in the graph or it is not |

---

## Question taxonomy

### Questions that favour SPARQL

These questions require precise set intersection, counting, or multi-hop
traversal — operations vector search cannot do reliably.

**Exact identifier lookup**
```
"Find all papers with UniProt protein P04637 (TP53)"
```
RAG embeds the accession as part of text. Exact match on `P04637` requires
the token to appear in the retrieved chunk — not guaranteed.
SPARQL: `WHERE { ?paper p9:mentions p9:protein_P04637 }`— always correct.

**Set intersection**
```
"Which papers mention both TP53 and BRCA1?"
```
RAG: retrieves papers about TP53 or BRCA1 — intersection is not guaranteed.
SPARQL:
```sparql
SELECT ?paper WHERE {
  ?paper p9:mentions p9:protein_TP53 .
  ?paper p9:mentions p9:protein_BRCA1 .
}
```

**Multi-hop traversal**
```
"Which diseases are associated with proteins mentioned in papers by Jane Smith?"
```
RAG: would need to retrieve papers by Jane Smith, then extract proteins, then
look up diseases — three retrieval steps, each adding noise.
SPARQL:
```sparql
SELECT DISTINCT ?disease WHERE {
  ?paper  p9:authored_by   p9:author_jane_smith ;
          p9:mentions      ?protein .
  ?protein p9:associated_with ?disease .
}
```

**Counting and aggregation**
```
"How many papers mention EGFR?"
```
RAG: cannot count. An LLM will guess or hallucinate a number.
SPARQL: `SELECT (COUNT(?paper) AS ?n) WHERE { ?paper p9:mentions p9:protein_EGFR }`

### Questions that favour RAG

These questions require synthesis, explanation, or reasoning over unstructured
text — things SPARQL cannot do.

**Explanation and synthesis**
```
"What is the role of TP53 in DNA damage response?"
```
SPARQL returns facts as triples — it cannot explain or synthesise. RAG retrieves
relevant passages and the LLM synthesises a coherent answer.

**Comparative and analogical**
```
"How does the role of TP53 in lung cancer differ from its role in glioblastoma?"
```
A graph can tell you which papers mention TP53 in each cancer type, but cannot
explain the biological difference. RAG can.

**Open-ended research questions**
```
"What are the current open questions in EGFR-targeted therapy resistance?"
```
There is no single fact that answers this. The answer requires synthesis across
many sources — exactly what RAG with a generative LLM does well.

---

## Benchmark design

The benchmark (`src/benchmark.py`) contains 20 questions split into two groups.

### Structured questions — 10 (SPARQL favoured)

Questions that require exact set operations, counting, or multi-hop graph
traversal. SPARQL answers are deterministic and treated as ground truth. RAG
answers are scored against the SPARQL result.

| # | Question | Requires |
|---|----------|----------|
| 1 | How many papers mention TP53? | COUNT aggregation |
| 2 | Which papers mention both TP53 and BRCA1? | Set intersection (JOIN) |
| 3 | Which proteins appear in more than 5 papers? | Aggregation + HAVING |
| 4 | Which EGFR papers were published after 2018? | Filter + date comparison |
| 5 | Which proteins are co-mentioned with TP53 in ≥3 papers? | Self-join + HAVING |
| 6 | Which authors published papers mentioning KRAS? | 2-hop traversal |
| 7 | Diseases linked to proteins in BRCA1 papers? | 3-hop traversal |
| 8 | Which paper mentions the most distinct proteins? | Aggregation + ORDER BY |
| 9 | Which papers are tagged with the oncology EDAM topic? | EDAM alignment query |
| 10 | Which papers mention both MDM2 and TP53? | Set intersection |

### Open-ended questions — 10 (RAG favoured)

Questions requiring synthesis, explanation, or analogical reasoning over
unstructured text. SPARQL is not applicable; recorded as N/A.

| # | Question |
|---|----------|
| 1 | Role of TP53 in the DNA damage response |
| 2 | How BRCA1 contributes to tumour suppression |
| 3 | Mechanisms by which EGFR drives cancer progression |
| 4 | How PTEN loss affects cancer cell survival |
| 5 | Relationship between MDM2 and TP53, and therapeutic exploitation |
| 6 | How ATM functions as a DNA damage sensor |
| 7 | Cancer types associated with KRAS mutations and why |
| 8 | Therapeutic strategies for BRCA1/2-deficient tumours |
| 9 | How EGFR signalling differs between lung and colorectal cancer |
| 10 | Clinical significance of RB1 loss in cancer |

### Scoring

- **Correctness** — is the answer factually right? (1.0 = fully correct)
- **Completeness** — does it cover all relevant facts? (1.0 = all facts present)
- **Hallucination** — does it state things not in the source data? (0.0 = none)

For structured questions: SPARQL result = ground truth (score 1.0 automatically).
RAG correctness is measured by entity overlap with the SPARQL result.

For open-ended questions: RAG answer is scored against the reference text in
`src/benchmark.py` using an LLM judge (or token-overlap heuristic).

## Benchmark results

*Run `python scripts/run_comparison.py` after deploying Fuseki and starting p7.*

```
python scripts/run_comparison.py
# Results written to results/comparison_<timestamp>.json
# Copy markdown table to this file.
```

| Question type | System | Correctness | Completeness | Hallucination |
|--------------|--------|------------|-------------|--------------|
| Structured (set intersection, counting) | SPARQL | — | — | — |
| Structured (set intersection, counting) | RAG | — | — | — |
| Open-ended (explanation, synthesis) | SPARQL | N/A | N/A | N/A |
| Open-ended (explanation, synthesis) | RAG | — | — | — |

---

## GraphRAG — next step

GraphRAG combines both approaches:
1. SPARQL traversal identifies the relevant entities and their relationships
2. Vector search retrieves the relevant passages for those entities
3. LLM synthesises an answer grounded in both the graph structure and the text

This handles the case where a question is partially structured ("which proteins
are mentioned in papers about glioblastoma") and partially open-ended ("and what
do we know about their function?"). See PROGRESS.md for the planned implementation.
