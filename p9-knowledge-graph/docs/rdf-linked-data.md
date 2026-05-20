# RDF and Linked Data
*p9 — Knowledge Graph & Semantic Search*

---

## Origin and motivation

In the early web, pages linked to each other but data was siloed. A protein
database, a disease database, and a drug database each had their own schema,
their own identifiers, and no way to query across them without custom ETL work.

Tim Berners-Lee proposed a solution in 1999: represent data the same way the
web represents pages — with universal identifiers (URIs) and a standard format
(RDF) so that any dataset could link to any other. He called this the
**Semantic Web**. The idea was that machines could traverse linked data the way
browsers traverse linked pages.

W3C standardised RDF in 1999, SPARQL (the query language) in 2008, and RDF 1.1
in 2014. The broader movement became known as **Linked Data** — open datasets
published with resolvable URIs so they could be interconnected.

---

## RDF — the data model

Every fact in RDF is a triple:

```
subject  →  predicate  →  object
```

Always exactly three parts. A knowledge graph is a collection of these triples.

```
<TP53>        associated_with  <Glioblastoma>
<Paper:12345> mentions         <TP53>
<Paper:12345> authored_by      "Jane Smith"
<Paper:12345> cites            <Paper:67890>
```

The power of this model: any fact can be expressed, and facts from different
datasets can be combined as long as they use the same URIs for the same things.

---

## URI — universal identity

URI (Uniform Resource Identifier) is a string that uniquely identifies a thing.
A URL is a type of URI — one you can fetch from. In RDF, URIs identify concepts:
things, relationships, properties — not just web pages.

```
http://purl.uniprot.org/uniprot/P04637     ← TP53 human protein
http://www.wikidata.org/entity/Q7186       ← Marie Curie
http://edamontology.org/topic_2640         ← Oncology (EDAM concept)
```

**Global uniqueness** is the key property. If two datasets both use
`http://purl.uniprot.org/uniprot/P04637` for TP53, they are provably talking
about the same thing. A SPARQL query can join them without any schema mapping.

This is what makes linked data different from traditional data integration:
identity is global by design, not something you negotiate per integration.

---

## Turtle — the file format

Turtle (Terse RDF Triple Language) is the most human-readable format for
writing RDF. The same triple in three formats:

**Turtle (.ttl)** — what we write and read:
```turtle
p9:paper_12345  p9:mentions  p9:protein_TP53 .
```

**XML/RDF (.rdf)** — verbose, machine-oriented:
```xml
<rdf:Description rdf:about="p9:paper_12345">
  <p9:mentions rdf:resource="p9:protein_TP53"/>
</rdf:Description>
```

**N-Triples (.nt)** — one triple per line, no shortcuts:
```
<http://portfolio/p9/paper_12345> <http://portfolio/p9/mentions> <http://portfolio/p9/protein_TP53> .
```

All three are equivalent. Turtle is preferred for authoring because subjects
can be grouped — semicolon means "same subject, next predicate", dot ends the
block:

```turtle
@prefix p9:   <http://portfolio/p9/> .
@prefix edam: <http://edamontology.org/> .

p9:paper_12345
    a              p9:Paper ;
    p9:pmid        "12345" ;
    p9:title       "TP53 mutations in glioblastoma" ;
    p9:year        "2024" ;
    p9:mentions    p9:protein_TP53 ;
    edam:has_topic edam:topic_2640 .    ← Oncology
```

The `@prefix` declarations define shorthand — `p9:paper_12345` expands to the
full URI `http://portfolio/p9/paper_12345`.

---

## SPARQL — querying the graph

SPARQL (SPARQL Protocol and RDF Query Language) is to RDF what SQL is to
relational databases. W3C standard since 2008 (SPARQL 1.1 in 2013).

It works by specifying a pattern of triples with variables (`?x`) and asking
the graph to find all assignments that match:

```sparql
SELECT ?paper ?disease WHERE {
  ?paper   p9:mentions        ?protein .
  ?protein p9:associated_with ?disease .
}
```

The engine finds every `(?paper, ?protein, ?disease)` combination where both
triples exist — a two-hop traversal across the graph. A vector store cannot
do this reliably.

SPARQL also supports aggregation, filtering, optional patterns, and federation
(querying multiple endpoints in one query):

```sparql
# Papers mentioning proteins associated with more than 3 diseases
SELECT ?paper (COUNT(?disease) AS ?n) WHERE {
  ?paper   p9:mentions        ?protein .
  ?protein p9:associated_with ?disease .
}
GROUP BY ?paper
HAVING (COUNT(?disease) > 3)
ORDER BY DESC(?n)
```

---

## The open linked data ecosystem

### Fully open — public URIs, public SPARQL endpoints

**Wikidata**
All Wikipedia structured data as RDF. Billions of triples. Public SPARQL
endpoint. All URIs resolve — `www.wikidata.org/entity/Q7186` returns Marie
Curie's full record as RDF, JSON, or HTML.

```sparql
# All women who won the Nobel Prize in Physics — runs live on Wikidata
SELECT ?person ?personLabel WHERE {
  ?person wdt:P166 wd:Q37922 .    # won Nobel Prize in Physics
  ?person wdt:P21  wd:Q6581072 .  # is female
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" }
}
```

**UniProt**
The entire protein database as RDF. Public SPARQL endpoint at
`sparql.uniprot.org`. Any protein record fetchable as Turtle:

```
https://rest.uniprot.org/uniprotkb/P04637.ttl
```

The response includes disease associations, GO terms, taxonomy, citations,
sequence features — all as triples. p9 downloads this directly rather than
converting from JSON.

**EBI (European Bioinformatics Institute)**
- **ChEMBL** — compounds and bioactivity data, public SPARQL endpoint
- **Ensembl** — gene data, RDF dumps downloadable
- **Reactome** — biological pathways as RDF

**Library of Congress**
Bibliographic data as linked data at `id.loc.gov`. Subject headings, name
authorities, classification schemes — all as RDF with public URIs.

### Partial — open vocabulary, distributed data

**Schema.org**
Google, Microsoft, and Yahoo defined Schema.org as a shared vocabulary for
structured data in web pages. The terms (`schema:author`, `schema:name`,
`schema:datePublished`) are open URIs anyone can use. But the actual data is
embedded in individual websites — there is no central SPARQL endpoint. Google
indexes it for rich search results; you cannot query it yourself.

**British Library**
Has published some linked data but coverage and endpoint reliability are
inconsistent compared to Library of Congress.

### Closed — internal use only

**Pharma (Pfizer, AstraZeneca, Roche)**
Use knowledge graphs internally for drug discovery — connecting compounds,
targets, diseases, clinical trials, literature. The technology is identical to
the open ecosystem (RDF, SPARQL, ontologies) but the data is proprietary. URIs
are internal, endpoints are behind firewalls. These graphs can have billions of
triples and are among the most valuable data assets in the industry.

---

## How p9 connects into this ecosystem

p9 does not build a closed graph. Paper triples reference UniProt URIs directly:

```turtle
p9:paper_12345  p9:mentions  <http://purl.uniprot.org/uniprot/P04637> .
```

This single triple connects p9's paper graph into UniProt's published graph. A
federated SPARQL query can traverse from a local paper → into UniProt's full
protein record → into disease associations → into GO terms, without p9 storing
any of that data locally:

```sparql
SELECT ?paper ?disease WHERE {
  ?paper p9:mentions ?protein .               # from p9's local graph
  SERVICE <https://sparql.uniprot.org/sparql> {
    ?protein up:annotation ?ann .              # from UniProt's public endpoint
    ?ann     a             up:Disease_Annotation ;
             rdfs:comment  ?disease .
  }
}
```

This is linked data working as intended — local data connecting into a global
web of open datasets.
