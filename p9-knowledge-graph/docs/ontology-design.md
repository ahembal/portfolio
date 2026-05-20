# Ontology Design
*p9 — Knowledge Graph & Semantic Search*

---

## Why align to existing ontologies

A knowledge graph with purely local terms (e.g. `p9:Paper`, `p9:mentions`) is
self-contained but isolated. Another system using different terms for the same
concepts cannot interoperate with it.

Ontology alignment solves this: by mapping local terms to established ontologies
(EDAM, OBI, schema.org), the graph becomes queryable alongside external datasets
that use the same terms. A SPARQL query using an EDAM topic term works the same
way whether the data comes from this graph or any other EDAM-aligned dataset.

In life science informatics this matters practically — EDAM and OBI are used by
databases, workflows, and registries across the field. Alignment is how data
becomes findable and reusable beyond the system that produced it.

---

## Ontologies used

### EDAM

EDAM (EMBRACE Data And Methods) is a domain ontology for bioinformatics
operations, data types, formats, and topics.

Relevant branches used in p9:

| EDAM concept | URI | Used for |
|-------------|-----|---------|
| `topic_2640` | Oncology | Cancer-related papers |
| `topic_0634` | Pathology | Disease entities |
| `topic_0622` | Genomics | Genomics papers |
| `topic_0602` | Molecular interactions, pathways and networks | Signalling pathway papers |
| `data_0896` | Protein report | UniProt protein records |
| `operation_0224` | Query and retrieval | SPARQL query operations |

Note: EDAM has no term for PubMed identifier (PMID). PMIDs are typed using
`schema:identifier` instead.

### OBI

OBI (Ontology for Biomedical Investigations) describes biological and clinical
investigations, assays, and study designs.

| OBI concept | URI | Used for |
|-------------|-----|---------|
| `OBI_0000070` | Assay | Experimental papers |
| `OBI_0000011` | Study design | Research design metadata |

### schema.org

Used for generic descriptive properties that don't require domain-specific terms:

| schema.org term | Used for |
|----------------|---------|
| `schema:name` | Human-readable label for any entity |
| `schema:identifier` | Generic identifier (PMID, UniProt accession) |
| `schema:author` | Paper authorship |
| `schema:datePublished` | Publication year |
| `schema:citation` | Citation relationship between papers |

---

## Local schema

The local namespace is `http://portfolio/p9/`. Local terms are used where no
suitable ontology term exists.

### Classes

| Local class | Aligned to | Description |
|-------------|-----------|-------------|
| `p9:Paper` | `schema:ScholarlyArticle` | A PubMed paper |
| `p9:Author` | `schema:Person` | A paper author |
| `p9:Protein` | `edam:data_0896` | A UniProt protein record ("Protein report") |
| `p9:Gene` | *(local)* | A gene — no suitable EDAM class term exists |
| `p9:Disease` | `edam:topic_0634` | A disease ("Pathology") |

### Properties

| Local property | Aligned to | Domain | Range |
|---------------|-----------|--------|-------|
| `p9:pmid` | `schema:identifier` | Paper | Literal |
| `p9:uniprot_id` | `schema:identifier` | Protein | Literal |
| `p9:gene_symbol` | `schema:name` | Gene | Literal |
| `p9:authored_by` | `schema:author` | Paper | Author |
| `p9:mentions` | *(local)* | Paper | Protein / Gene |
| `p9:cites` | `schema:citation` | Paper | Paper |
| `p9:associated_with` | *(local)* | Protein | Disease |
| `p9:encodes` | *(local)* | Gene | Protein |
| `p9:has_topic` | `edam:has_topic` | Paper | EDAM Topic |

`p9:mentions` and `p9:associated_with` have no direct equivalent in standard
ontologies at the right granularity — defining them locally is the correct choice
rather than forcing a misaligned mapping.

---

## Design decisions

### Why EDAM over pure OWL

EDAM is a controlled vocabulary with a flat-enough structure to align practically.
A full OWL ontology (Gene Ontology, Disease Ontology) would require reasoning
infrastructure and is out of scope for this project. EDAM gives interoperability
at the topic and data type level without requiring an OWL reasoner.

### Why not use existing ontologies for relationships

`p9:mentions` (Paper → Protein) and `p9:associated_with` (Protein → Disease) are
local because:

- "Mentions" in a paper is not the same as a formal biological assertion. A paper
  mentioning TP53 does not mean TP53 is functionally involved — it might appear
  in a comparison table or a background section.
- Using a formal ontology property (e.g. RO:0002206, "expressed in") would imply
  a biological claim the data does not support.

Local properties with clear documentation are more honest than misaligned
ontology terms.

### Literal identifiers vs URI nodes

PubMed IDs and UniProt accessions are stored as both:
- A URI node (e.g. `p9:protein_P04637`) as the subject of triples
- A literal string property (e.g. `p9:uniprot_id "P04637"`) for exact matching

This allows SPARQL queries to either traverse relationships (`?paper p9:mentions
p9:protein_P04637`) or filter on identifiers (`FILTER(?uid = "P04637")`).
