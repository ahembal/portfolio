# How It Works
*p9 — Knowledge Graph & Semantic Search*

---

## What is a knowledge graph

A knowledge graph stores facts as triples: **subject → predicate → object**.

```
<Paper:PMID12345>  authored_by     <Author:JaneSmith>
<Paper:PMID12345>  mentions        <Protein:TP53>
<Protein:TP53>     associated_with <Disease:Glioblastoma>
<Paper:PMID12345>  cites           <Paper:PMID67890>
```

Every fact is explicit and structured. There is no ambiguity — either the triple
exists or it does not. This is fundamentally different from a vector store, where
a document "about TP53" might or might not mention glioblastoma explicitly, and
retrieval is based on semantic proximity rather than stated facts.

---

## RDF — the data model

The triples are stored in RDF (Resource Description Framework). Each node in the
graph is identified by a URI. Predicates are also URIs, often borrowed from
established ontologies.

```turtle
@prefix p9:   <http://portfolio/p9/> .
@prefix edam: <http://edamontology.org/> .
@prefix obi:  <http://purl.obolibrary.org/obo/OBI_> .

p9:paper_12345
    a                    p9:Paper ;
    p9:pmid              "12345" ;
    p9:title             "TP53 mutations in glioblastoma" ;
    p9:mentions          p9:protein_tp53 ;
    p9:cites             p9:paper_67890 ;
    edam:has_topic       edam:topic_2640 .   ← Oncology (EDAM term)

p9:protein_tp53
    a                    p9:Protein ;
    p9:uniprot_id        "P04637" ;
    p9:gene_symbol       "TP53" ;
    p9:associated_with   p9:disease_glioblastoma .
```

The `edam:has_topic edam:topic_2640` triple connects a local entity to a term in
the EDAM ontology. This is ontology alignment — it makes the graph interoperable
with external datasets that also use EDAM terms.

---

## SPARQL — querying the graph

SPARQL is a query language for RDF graphs. It works by specifying a pattern of
triples and asking the graph to find all combinations of variables that match.

**Simple query — all papers mentioning TP53:**
```sparql
SELECT ?paper ?title WHERE {
  ?paper p9:mentions p9:protein_tp53 ;
         p9:title    ?title .
}
```

**Multi-hop query — diseases connected to a paper through a protein:**
```sparql
SELECT ?paper ?protein ?disease WHERE {
  ?paper   p9:mentions        ?protein .
  ?protein p9:associated_with ?disease .
  ?paper   p9:title           ?title .
  FILTER(CONTAINS(?title, "glioblastoma"))
}
```

**Aggregation — top proteins by number of papers mentioning them:**
```sparql
SELECT ?protein (COUNT(?paper) AS ?count) WHERE {
  ?paper p9:mentions ?protein .
}
GROUP BY ?protein
ORDER BY DESC(?count)
LIMIT 10
```

RAG cannot answer any of these reliably. A vector search might find papers about
TP53 and papers about glioblastoma, but it cannot traverse the graph to find which
proteins are shared between those papers, or count relationships precisely.

---

## The data model

### Entities

| Entity | Description | Source |
|--------|-------------|--------|
| Paper | PubMed abstract with PMID, title, year, journal | PubMed API |
| Author | Name and affiliation | PubMed API |
| Protein | UniProt record with accession, gene symbol, function | UniProt API |
| Gene | Gene symbol and organism | PubMed/UniProt |
| Disease | Disease name and MeSH identifier | MeSH via PubMed |
| Topic | EDAM topic term | EDAM ontology |

### Relationships

| Relationship | From | To | Meaning |
|-------------|------|----|---------|
| `authored_by` | Paper | Author | Paper was written by this author |
| `mentions` | Paper | Protein / Gene | Paper explicitly mentions this entity |
| `cites` | Paper | Paper | Paper cites another paper |
| `associated_with` | Protein | Disease | Protein is implicated in this disease |
| `has_topic` | Paper | EDAM Topic | Paper belongs to this research topic |
| `encodes` | Gene | Protein | Gene encodes this protein |

---

## System architecture

```
PubMed API ──┐
              ├──► builder.py ──► RDF graph (.ttl) ──► Fuseki ──► SPARQL endpoint
UniProt API ──┘         │
                        └──► aligner.py ──► EDAM / OBI alignment
                                                         │
                                                sparql.py (query interface)
                                                         │
                                              queries/ (example queries)
```

**builder.py** fetches papers and proteins from PubMed and UniProt, extracts
entities and relationships, and serialises them as RDF triples in Turtle format.

**aligner.py** maps local entity types to EDAM and OBI concepts, adding
ontology-aligned predicates to the graph.

**Fuseki** loads the Turtle file and exposes a SPARQL HTTP endpoint. Running in
the cluster on quick-thrush, accessible via NodePort.

**sparql.py** provides a Python interface to the Fuseki endpoint — query
execution, result parsing, and integration with p7's evaluation framework for
the RAG vs SPARQL comparison.

---

## How this extends p6 and p7

p6 uses PubMed and UniProt as live API sources — fetching on demand per query.
p7 embeds the same corpus in a vector store for semantic retrieval.

p9 structures the same data as a graph. The three approaches answer different
questions best:

| Question type | Best approach |
|--------------|---------------|
| "Explain what TP53 does" | RAG (p6/p7) — open-ended, needs synthesis |
| "Which papers mention both TP53 and BRCA1?" | SPARQL (p9) — exact set intersection |
| "What diseases are linked to proteins in this paper?" | SPARQL (p9) — multi-hop traversal |
| "Find papers similar in topic to this abstract" | Vector search (p7) — semantic similarity |

See `docs/comparison.md` for a structured evaluation across these question types.
