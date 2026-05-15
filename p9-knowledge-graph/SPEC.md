# P9 — Knowledge Graph & Semantic Search

## What and why

p6 and p7 built a RAG system for life science research — retrieving relevant
passages from PubMed and answering questions. RAG works well for unstructured
text but has a fundamental limitation: it cannot reliably answer questions about
structured relationships. "Which imaging services in Europe support super-resolution
and are accessible to external researchers?" is a graph query, not a text search.

This project builds a knowledge graph over structured domain data, exposes it via
SPARQL, and compares it against the vector-based retrieval in p7. The central
question: when is a knowledge graph better than RAG, and when is it worse?

This is directly relevant to production systems like Euro-BioImaging's AI4Access
Research Navigator — where an LLM must reliably query a catalogue of hundreds of
scientific services with structured attributes, capabilities, and constraints.

---

## Problem statement

Three problems:

1. **RAG hallucinates relationships** — a vector store can find documents about
   a topic but cannot reliably answer "which X has property Y AND is related to Z."
   Knowledge graphs answer this precisely via SPARQL.

2. **Ontology alignment is unsolved in most portfolios** — connecting domain data
   to existing life science ontologies (EDAM, OBI, schema.org) makes data interoperable
   with the broader semantic web ecosystem. Most ML engineers have never done this.

3. **GraphRAG is emerging** — combining knowledge graph traversal with vector
   retrieval (GraphRAG) outperforms pure RAG on multi-hop questions. Building and
   evaluating this combination is a differentiating skill.

---

## What to build

### 1. Domain knowledge graph

A knowledge graph over two domains:

**Life science services** (modelled after Euro-BioImaging):
- Imaging facilities with capabilities, locations, access conditions
- Techniques (confocal, super-resolution, cryo-EM, etc.)
- Sample types supported
- Relationships between facilities, techniques, and resources

**Research literature** (from p6/p7 corpus):
- Papers with authors, journals, topics, genes/proteins mentioned
- Citations between papers
- Relationships between proteins and diseases (from UniProt)

### 2. Ontology alignment

Map the knowledge graph to existing ontologies:
- **EDAM** — bioinformatics operations and data types
- **OBI** — biomedical investigations ontology
- **schema.org** — for generic service descriptions

This makes the graph interoperable — SPARQL queries can traverse both local
and external linked data.

### 3. SPARQL endpoint

Expose the knowledge graph via a SPARQL endpoint (Apache Jena Fuseki or
equivalent). Implement example queries that demonstrate what graphs can answer
that RAG cannot:

```sparql
# Which facilities support both super-resolution and cryo-EM and are in Sweden?
SELECT ?facility WHERE {
  ?facility :supports :SuperResolution .
  ?facility :supports :CryoEM .
  ?facility :location :Sweden .
}
```

### 4. GraphRAG — hybrid retrieval

Combine knowledge graph traversal with the vector search from p7:
- Graph traversal identifies relevant entities and relationships
- Vector search retrieves relevant passages for context
- LLM synthesises an answer grounded in both

Compare against pure RAG (p7) on a fixed benchmark:
- Multi-hop questions (benefit from graph)
- Factual relationship questions (benefit from graph)
- Open-ended questions (benefit from RAG)

### 5. Evaluation

Extend the p7 evaluation framework to compare:
- Pure RAG (p7 baseline)
- Pure SPARQL (structured queries only)
- GraphRAG (combined)

Metrics: faithfulness, answer relevance, and a new metric — **structural
correctness** (does the answer accurately reflect the graph relationships?).

---

## Repository layout

```
p9-knowledge-graph/
├── SPEC.md
├── PROGRESS.md
├── data/
│   ├── ontologies/         ← EDAM, OBI, schema.org fragments
│   └── seed/               ← seed triples for the knowledge graph
├── src/
│   ├── builder.py          ← constructs RDF graph from structured sources
│   ├── aligner.py          ← maps local terms to ontology concepts
│   ├── sparql.py           ← SPARQL query interface
│   └── graphrag.py         ← combined graph + vector retrieval
├── fuseki/
│   └── config.ttl          ← Apache Jena Fuseki configuration
└── docs/
    ├── how-it-works.md
    ├── ontology-design.md  ← design decisions for the graph schema
    └── comparison.md       ← RAG vs SPARQL vs GraphRAG results
```

---

## What this demonstrates

- **RDF/OWL** — modelling domain knowledge formally with triples and ontologies
- **SPARQL** — precise structured queries over a knowledge graph
- **Ontology alignment** — connecting to EDAM, OBI — standard in life science informatics
- **GraphRAG** — state-of-the-art hybrid retrieval combining graphs and vectors
- **Comparative evaluation** — knowing when to use which approach is the senior skill

---

## Relationship to other projects

| Project | Connection |
|---------|-----------|
| p6 | Shares the PubMed/UniProt data sources — p9 structures them as a graph |
| p7 | p7 is the RAG baseline — p9 extends it with graph retrieval and compares |
| p8 | Model registry entries are structured data that can be represented as RDF |

---

## Out of scope

- Training a custom embedding model for graph entities
- Full production deployment of Fuseki (demo only)
- Coverage of all life science ontologies (focus on EDAM + OBI)
- Real Euro-BioImaging service data (synthetic data modelled after it)
