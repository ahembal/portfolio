# Graphs — Concepts and Types
*p9 — Knowledge Graph & Semantic Search*

---

## What is a graph

A graph is a data structure made of two things:

- **Nodes** — the entities (a paper, a protein, a disease, a person, a service)
- **Edges** — the relationships between them (mentions, authored_by, associated_with)

Every edge has a direction and a label. The label says what the relationship means.

```
[Paper: "BRCA1 mutations in breast cancer"]
        │
        │ mentions
        ▼
[Protein: BRCA1]
        │
        │ associated_with
        ▼
[Disease: breast cancer]
```

This is fundamentally different from a table (rows and columns) or a document store
(JSON blobs). In a table, relationships are encoded as foreign keys and require joins.
In a graph, relationships are first-class citizens — traversing them is the primary
operation.

---

## The graph in p9

p9 uses a **knowledge graph** over biomedical research literature.

Nodes: Papers (PubMed), Proteins (UniProt), Diseases, Authors
Edges: p9:mentions, up:annotation, schema:author, edam:has_topic

The graph is stored in **RDF** (Resource Description Framework) — every edge is a
triple: subject → predicate → object. The database is **Apache Jena Fuseki**, which
exposes a SPARQL query endpoint. See `docs/how-it-works.md` for the full data model.

The graph enables queries that a vector store cannot answer:
- Set intersection: which papers mention both TP53 AND BRCA1?
- Multi-hop traversal: which diseases are linked to proteins mentioned in BRCA1 papers?
- Aggregation: which proteins appear in more than 5 papers?

---

## Types of graphs

### Knowledge graph

A general-purpose network of entities and relationships. Nodes can be anything.
Relationships are explicit, labelled, and queryable. The point is to make structured
knowledge machine-readable and traversable.

**Examples:**
- Wikidata — all Wikipedia structured data as a knowledge graph (billions of triples)
- UniProt — proteins, diseases, GO terms, citations as RDF
- p9 — papers, proteins, diseases, EDAM topics

**Used for:** question answering, semantic search, structured data integration,
reasoning over relationships.

---

### Provenance chain

A specific type of graph focused on tracking the origin and history of something.
Answers: "where did this come from, and what happened to it along the way?"

**Example — MSMdad (Bigpicture):**

```
Biological Being → Case → Specimen → Block → Slide → Image → Annotation → Dataset
```

Each arrow records a transformation or derivation. The full chain tells you: this
digital image came from this tissue block, which was taken from this specimen, which
came from this patient, under these clinical conditions.

Provenance chains are critical in biomedical research for:
- Regulatory compliance (tracing data back to consent)
- Reproducibility (knowing exactly what was done at each step)
- Quality control (identifying where errors were introduced)

PROV-O is the W3C standard ontology for provenance graphs.

---

### Ontology graph

A formal definition of concepts and their relationships in a domain. Not about
data instances — about the vocabulary itself.

**Example — EDAM:**
```
data_0896 (Protein report)
    └── is_a → data_2048 (Report)
                   └── is_a → data (Data)

topic_2640 (Oncology)
    └── is_a → topic_0621 (Molecular biology)
```

Each concept has a URI, a definition, and "is_a" / "part_of" relationships to other
concepts. Using EDAM URIs in your data ("this paper has_topic Oncology") makes your
data interoperable with any other system that uses the same URIs.

Other ontologies in this space:
- **OBI** (Ontology for Biomedical Investigations) — assays, protocols, study designs
- **Gene Ontology (GO)** — biological processes, molecular functions, cellular components
- **SNOMED CT** — clinical medicine concepts
- **Dublin Core** — bibliographic metadata

---

### Citation graph

Papers as nodes, citations as directed edges. If paper A cites paper B, there is an
edge A → B.

Used in:
- Academic impact measurement (h-index, PageRank-based metrics)
- Research trend analysis
- Finding influential foundational papers

p9 has citation relationships embedded in it — UniProt protein records cite their
key papers, creating a protein → paper → (implicitly) paper citation subgraph.

---

### Social graph

People as nodes, social relationships as edges (follows, knows, collaborates with).

**Examples:** LinkedIn connections, Twitter/X follows, co-authorship networks.

Used for: recommendations, community detection, influence analysis.

---

### Dependency graph

Nodes are components (software packages, pipeline tasks, services). Edges represent
dependencies — "X requires Y", "X must run before Y".

**Examples:**
- `npm install` resolves a package dependency graph before installing
- Airflow DAGs are dependency graphs for data pipeline tasks
- Git commits form a dependency graph (each commit points to its parent)

---

### DAG — Directed Acyclic Graph

A directed graph with no cycles — you can never follow edges and return to the same
node. A strict mathematical property.

Most pipeline orchestrators (Airflow, Prefect, Dagster) require DAGs because cycles
would mean infinite loops. Git history is a DAG. Package dependencies must be DAGs
(circular dependencies are errors).

---

### Tree

A special case of a DAG: each node has exactly one parent (except the root). No
branching in the upward direction.

**Examples:** file systems, HTML DOM, organisation charts, decision trees in ML.

A tree is a graph. A DAG is a graph. A knowledge graph is a graph. They differ in
what constraints they impose on structure.

---

## Why graphs for service discovery in research infrastructure

Answering questions like "which imaging facilities support cryo-EM and accept
external users?" requires set intersection across structured relationships — not
text similarity. A vector store retrieves documents that are *about* the query
topic. It cannot reliably answer "facility supports BOTH technique A AND technique B."

A knowledge graph answers this precisely:

```sparql
SELECT ?facility WHERE {
  ?facility  :located_in    :Sweden .
  ?facility  :supports      :CryoEM .
  ?facility  :access_type   :ExternalUsers .
}
```

A service catalogue for research infrastructure naturally involves all three graph
types working together:
- **Knowledge graph** — the services, facilities, techniques and their relationships
- **Provenance chain** — which node reported what capability, when, verified by whom
- **Ontology** — the shared vocabulary (EDAM operation terms for techniques, schema.org
  for services and organisations) that makes entries from different sources interoperable
