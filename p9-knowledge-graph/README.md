# p9 — Knowledge Graph & Semantic Search

RDF knowledge graph over PubMed papers and UniProt proteins, exposed as a SPARQL endpoint on Kubernetes — with a structured comparison against the vector RAG system in p7.

## What it demonstrates

- RDF knowledge graph construction: 10 seed proteins → UniProt-inverted citations → PubMed papers → 131k triples
- SPARQL for multi-hop reasoning: queries RAG cannot answer — set intersection, aggregation, 3-hop traversal
- Ontology alignment: EDAM topic and data type alignment for interoperability with external life science datasets
- RAG vs SPARQL comparison: same 20 questions answered by both systems, scored by p7's LLM judge

## Live endpoint

```bash
# Papers mentioning both TP53 and BRCA1
curl -X POST http://<node-ip>:30900/p9/sparql \
  -H "Content-Type: application/sparql-query" \
  -d 'PREFIX p9: <http://portfolio/p9/>
      PREFIX uprot: <http://purl.uniprot.org/uniprot/>
      SELECT ?title WHERE {
        ?paper p9:mentions uprot:P04637, uprot:P38398 ;
               <https://schema.org/name> ?title .
      }'
```

## Key design decisions

- **UniProt-inverted citations** — instead of NLP, the graph is seeded by inverting UniProt's embedded PubMed citation links. Fully deterministic, connects into the linked data ecosystem.
- **UniProt pubmed URIs as paper nodes** — paper nodes use `purl.uniprot.org/pubmed/PMID` so UniProt's `up:citation` edges connect directly without OWL inference.
- **EDAM alignment** — papers get `edam:has_topic` triples based on title keyword matching; proteins get `edam:data_0896`; diseases get `edam:topic_0634`.

## Stack

| Component | Choice |
|-----------|--------|
| Graph format | RDF (Turtle) |
| SPARQL endpoint | Apache Jena Fuseki 4.8.0 (`stain/jena-fuseki`) |
| Graph builder | `rdflib`, TIAToolbox UniProt client |
| Ontology | EDAM, OBI, schema.org |
| Deployment | Helm chart, NodePort 30900, TDB2 persistent dataset |
| Storage | graph.ttl in Ceph RGW, loaded at pod startup |

See [`docs/how-it-works.md`](docs/how-it-works.md) for the full architecture and [`docs/ontology-design.md`](docs/ontology-design.md) for alignment decisions.

## Related

- **[p6](../p6-research-agent/)** — the research agent that uses PubMed/UniProt as live sources
- **[p7](../p7-rag-evaluation/)** — the RAG system compared against SPARQL in the benchmark
