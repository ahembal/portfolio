# How It Works
*p9 — Knowledge Graph & Semantic Search*

---

## Background concepts

### RDF

RDF (Resource Description Framework) is a standard for representing facts as
triples. Defined by the W3C in 1999, standardised as RDF 1.1 in 2014. It was
originally designed to make the web machine-readable — Tim Berners-Lee's vision
of a "Semantic Web" where data, not just pages, could be linked and queried
across institutions.

Every fact in RDF has exactly this structure:

```
subject  →  predicate  →  object
```

Always triples — that is the fundamental constraint. A knowledge graph is a
large collection of these triples.

RDF is used in production by Wikidata (billions of triples from Wikipedia),
UniProt (all protein data), EBI (Ensembl, ChEMBL), Schema.org (structured data
in Google/Bing search results), and national libraries worldwide. In life science
it became standard infrastructure because datasets — genes, proteins, diseases,
compounds — naturally connect across institutional boundaries, and RDF's identity
model makes those connections explicit without requiring a central database.

### URI

URI (Uniform Resource Identifier) is a string that uniquely identifies a thing.
A URL is a type of URI — one you can fetch from. In RDF, URIs identify concepts,
not just web pages: things, relationships, properties.

```
https://www.wikidata.org/entity/Q7186    ← Marie Curie
https://www.wikidata.org/prop/P166       ← "award" relationship
https://www.wikidata.org/entity/Q37922   ← Nobel Prize in Physics
```

The key property is **global uniqueness**: if two datasets both use the same URI
for "Nobel Prize in Physics", they are talking about the same thing and can be
joined in a single query — no schema mapping, no ETL. This is what makes
ontology alignment practical.

In Turtle files URIs are shortened with prefixes:
```turtle
wd:Q7186  wdt:P166  wd:Q37922 .
# expands to:
# <https://www.wikidata.org/entity/Q7186>
#   <https://www.wikidata.org/prop/P166>
#   <https://www.wikidata.org/entity/Q37922> .
```

### Real Wikidata triples — Marie Curie

```turtle
wd:Q7186  wdt:P31   wd:Q5        # Marie Curie  instance-of     human
wd:Q7186  wdt:P21   wd:Q6581072  # Marie Curie  sex-or-gender   female
wd:Q7186  wdt:P27   wd:Q142      # Marie Curie  country         France
wd:Q7186  wdt:P27   wd:Q36       # Marie Curie  country         Poland
wd:Q7186  wdt:P166  wd:Q37922    # Marie Curie  award           Nobel Prize in Physics
wd:Q7186  wdt:P166  wd:Q11047    # Marie Curie  award           Nobel Prize in Chemistry
wd:Q7186  wdt:P569  "1867-11-07" # Marie Curie  date-of-birth   1867-11-07
```

Notice that "female", "France", and "Nobel Prize in Physics" are all URIs —
nodes in the graph with their own triples. Everything is a node or a literal.

A SPARQL query over this graph — all women who won the Nobel Prize in Physics:
```sparql
SELECT ?person ?personLabel WHERE {
  ?person wdt:P166 wd:Q37922 .    # won Nobel Prize in Physics
  ?person wdt:P21  wd:Q6581072 .  # and is female
}
```

Wikidata's public SPARQL endpoint answers this across billions of triples in
milliseconds. p9 uses the same model at a smaller scale.

### SPARQL

SPARQL (SPARQL Protocol and RDF Query Language) is to RDF what SQL is to
relational databases. W3C standard since 2008 (SPARQL 1.1 in 2013).

It works by specifying a pattern of triples with variables, and asking the graph
to find all assignments of those variables that match:

```sparql
SELECT ?paper ?disease WHERE {
  ?paper   p9:mentions        ?protein .  # paper mentions some protein
  ?protein p9:associated_with ?disease .  # that protein is associated with a disease
}
```

The graph engine finds every combination of `?paper`, `?protein`, `?disease`
where both triples exist. This is a two-hop traversal — something a vector store
cannot do reliably.

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
