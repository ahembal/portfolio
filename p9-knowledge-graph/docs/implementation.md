# Implementation
*p9 — Knowledge Graph & Semantic Search*

---

## Stack

| Component | Tool | Why |
|-----------|------|-----|
| RDF library | rdflib (Python) | Standard Python RDF library, supports Turtle/JSON-LD/N-Triples, no external service needed for graph construction |
| SPARQL endpoint | Apache Jena Fuseki | Mature, well-documented, runs as a single JAR or Docker container, production-grade SPARQL 1.1 support |
| Data sources | PubMed E-utilities API, UniProt REST API | Same sources as p6 — reuses existing tool patterns |
| Deployment | Kubernetes (quick-thrush), Helm chart | Consistent with all other portfolio services |
| Query interface | sparql.py (SPARQLWrapper) | Thin Python wrapper over Fuseki HTTP endpoint |

---

## Building the graph

### builder.py

Fetches structured data from PubMed and UniProt and serialises it as RDF triples.

**Step 1 — Fetch papers from PubMed**

Uses the E-utilities API (same pattern as p6's `pubmed_search` tool):
- Search for a configurable set of topics (e.g. "TP53 cancer", "BRCA1 repair")
- Fetch full records for the top N results per topic
- Extract: PMID, title, abstract, authors, journal, year, MeSH terms

**Step 2 — Fetch proteins from UniProt**

For each gene/protein mentioned in the fetched papers:
- Query UniProt REST API for the canonical human record
- Extract: UniProt accession, gene symbol, function summary, associated diseases

**Step 3 — Build RDF graph**

```python
from rdflib import Graph, Namespace, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

P9   = Namespace("http://portfolio/p9/")
EDAM = Namespace("http://edamontology.org/")
SCH  = Namespace("https://schema.org/")

g = Graph()
g.bind("p9",   P9)
g.bind("edam", EDAM)
g.bind("schema", SCH)

paper_uri = P9[f"paper_{pmid}"]
g.add((paper_uri, RDF.type,    P9.Paper))
g.add((paper_uri, P9.pmid,     Literal(pmid, datatype=XSD.string)))
g.add((paper_uri, P9.title,    Literal(title)))
g.add((paper_uri, EDAM.has_topic, EDAM[edam_topic]))
```

**Step 4 — Align and serialise**

`aligner.py` adds ontology-aligned triples on top of the local graph, then the
full graph is serialised to `data/seed/graph.ttl` in Turtle format.

```python
g.serialize("data/seed/graph.ttl", format="turtle")
```

---

## Fuseki deployment

### Local (development)

```bash
docker run -p 3030:3030 \
  -v $(pwd)/data/seed:/fuseki/data \
  -e ADMIN_PASSWORD=admin \
  stain/jena-fuseki \
  --update --loc /fuseki/data /p9
```

SPARQL endpoint available at `http://localhost:3030/p9/sparql`.

### Cluster (Helm)

The Helm chart in `helm/` deploys Fuseki as a Deployment with:
- A ConfigMap mounting `fuseki/config.ttl`
- An InitContainer that loads `graph.ttl` into Fuseki on startup
- A NodePort Service for access from outside the cluster

```
kubectl get svc -n knowledge-graph
NAME      TYPE       PORT(S)
fuseki    NodePort   3030:30900/TCP
```

The graph is loaded from a ConfigMap (for small graphs) or a PVC (for larger
graphs). For the seed data (~500 papers, ~200 proteins) a ConfigMap is sufficient.

---

## Query interface (sparql.py)

```python
from SPARQLWrapper import SPARQLWrapper, JSON

sparql = SPARQLWrapper("http://localhost:3030/p9/sparql")

def query(sparql_string: str) -> list[dict]:
    sparql.setQuery(sparql_string)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    return results["results"]["bindings"]
```

Used by the comparison framework to run the same questions through both SPARQL
(p9) and RAG (p7) and compare the results.

---

## Data volume and graph size

Estimated for the research literature seed dataset:

| Entity type | Count | Triples (approx) |
|-------------|-------|-----------------|
| Papers | ~500 | ~5,000 |
| Authors | ~1,500 | ~3,000 |
| Proteins | ~200 | ~2,000 |
| Diseases | ~100 | ~500 |
| Citation edges | ~1,000 | ~1,000 |
| Ontology alignment triples | — | ~2,000 |
| **Total** | | **~13,500** |

This is a small graph by any standard. Fuseki handles millions of triples
comfortably — the seed data fits entirely in memory.

---

## Reproducibility

The full graph can be rebuilt from scratch:

```bash
python src/builder.py --topics "TP53 cancer,BRCA1 repair,EGFR signalling" \
                      --papers-per-topic 100 \
                      --output data/seed/graph.ttl
```

The builder fetches live data from PubMed and UniProt, so results vary slightly
as new papers are published. The committed `graph.ttl` is a fixed snapshot used
for the benchmark comparison in `docs/comparison.md`.
