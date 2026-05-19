# P9 — Knowledge Graph & Semantic Search

## What and why

p6 and p7 built a RAG system for life science research. RAG works well for
unstructured text but cannot reliably answer questions about structured
relationships — "which papers mention both TP53 and glioblastoma, and what
proteins do they share?" is a graph query, not a text search.

This project builds a knowledge graph over research literature (papers,
proteins, diseases, genes from PubMed and UniProt), exposes it via SPARQL,
and compares structured graph queries against the vector retrieval in p7.

## What to build

- RDF knowledge graph over research literature (papers, proteins, diseases, genes)
- Ontology alignment to EDAM and OBI
- Apache Jena Fuseki SPARQL endpoint, deployed on the cluster
- SPARQL query examples demonstrating multi-hop reasoning RAG cannot do
- Comparison of RAG vs SPARQL on structured vs open-ended questions

## Repository layout

```
p9-knowledge-graph/
├── SPEC.md
├── PROGRESS.md
├── data/
│   ├── ontologies/         ← EDAM, OBI fragments
│   └── seed/               ← seed triples (Turtle format)
├── src/
│   ├── builder.py          ← constructs RDF graph from PubMed/UniProt data
│   ├── aligner.py          ← maps local terms to ontology concepts
│   └── sparql.py           ← SPARQL query interface
├── fuseki/
│   └── config.ttl          ← Apache Jena Fuseki configuration
├── helm/                   ← Helm chart for cluster deployment
├── queries/                ← SPARQL query examples
└── docs/
    ├── how-it-works.md
    ├── implementation.md
    ├── ontology-design.md
    └── comparison.md
```

## Out of scope

- GraphRAG (graph + vector hybrid retrieval) — planned as next step in PROGRESS.md
- Imaging facilities domain — planned as next step in PROGRESS.md
- Full production Fuseki deployment (demo only)
- Coverage of all life science ontologies (EDAM + OBI only)
