# Phase 7 — Imaging Facilities Knowledge Graph
*p9 extension — added 2026-05-27*

---

## What this adds

Phase 7 extends the p9 knowledge graph with a second domain layer: the European
research imaging infrastructure. Where Phases 1–6 cover biomedical literature
and proteins, Phase 7 covers the institutions, initiatives, facilities, and
techniques that make imaging-based research possible.

The two layers are kept in the same Fuseki triplestore and share the `p9:`
namespace. They can be queried independently or joined — e.g. "which facilities
offer techniques related to the EDAM topics covered by the protein papers in
Phase 1?"

---

## Entities

### Institution
A research organisation that hosts one or more imaging facilities.

Examples: SciLifeLab, EMBL, Karolinska Institutet, DKFZ, Institut Curie.

| Property | Ontology term | Notes |
|----------|--------------|-------|
| name | `schema:name` | |
| country | `schema:addressCountry` | ISO 3166-1 alpha-2 |
| type | `schema:ResearchOrganization` | |
| homepage | `schema:url` | |

### Initiative
A pan-European research infrastructure or network that institutions belong to.

Examples: Euro-BioImaging, ELIXIR, ESFRI, Bigpicture, GDI.

| Property | Ontology term | Notes |
|----------|--------------|-------|
| name | `schema:name` | |
| scope | `p9:initiativeScope` | local term — no schema.org equivalent |
| homepage | `schema:url` | |

### Facility
A physical imaging facility operated by an institution. A facility is a node
in one or more initiatives.

| Property | Ontology term | Notes |
|----------|--------------|-------|
| name | `schema:name` | |
| city | `schema:addressLocality` | |
| accessType | `p9:accessType` | PHYSICAL / REMOTE / BOTH |
| partOf | `schema:parentOrganization` | → Institution |
| nodeOf | `p9:nodeOf` | → Initiative |

### Technique
An imaging or analysis technique offered by a facility.

| Property | Ontology term | Notes |
|----------|--------------|-------|
| name | `schema:name` | |
| edamTopic | `edam:has_topic` | EDAM topic alignment |
| offeredBy | `p9:offeredBy` | → Facility |

---

## Relationships

```
Initiative ──< Facility       (p9:nodeOf — facility is a node of initiative)
Institution ──< Facility      (schema:parentOrganization)
Facility ──< Technique        (p9:offeredBy)
Technique ──> EDAM topic      (edam:has_topic)
Institution ──> Institution   (p9:partOf — e.g. NBIS is part of SciLifeLab)
```

---

## EDAM alignment for techniques

| Technique | EDAM topic |
|-----------|-----------|
| Light microscopy / confocal | topic_3382 — Light microscopy |
| Electron microscopy | topic_0611 — Electron microscopy |
| Biomedical imaging | topic_3384 — Medical imaging |
| Correlative microscopy | topic_3383 — Correlative microscopy |
| Image analysis | topic_3372 — Data visualisation |
| Cryo-EM | topic_1317 — Structural biology |
| Flow cytometry | topic_2229 — Cell biology |
| Expansion microscopy | topic_3382 — Light microscopy |

---

## Seed data

15–20 facilities from publicly available Euro-BioImaging node listings.
Data is derived from public sources only (eurobioimaging.eu, scilifeLab.se,
embl.org, institution websites).

Institutions covered: SciLifeLab, EMBL Heidelberg, Karolinska Institutet,
DKFZ, Institut Curie, KU Leuven, University of Helsinki, DTU Biosustain,
University of Oslo, Czech Centre for Phenogenomics.

---

## SPARQL queries

Phase 7 adds 5 queries to the existing query set:

| # | Query | What it demonstrates |
|---|-------|---------------------|
| 09 | Facilities offering confocal microscopy | Basic graph traversal: Technique → Facility |
| 10 | Techniques available in Sweden | Multi-hop: country filter via Institution → Facility → Technique |
| 11 | Remote-access facilities in Europe | Property filter on accessType |
| 12 | Institutions that are both ELIXIR and Euro-BioImaging nodes | Multi-initiative membership |
| 13 | Cross-domain join: EDAM topics in paper graph vs facility graph | Joins Phase 1–6 with Phase 7 |

Query 13 is the key one — it demonstrates why having both layers in the same
triplestore is more powerful than two separate systems.

---

## What this is NOT

Phase 7 is a static knowledge graph seeded from public data. It is not:
- A submission or registry system (no REST API, no inbox pattern)
- A dynamic graph (data does not grow at runtime)
- A replacement for any production facility registry

The goal is to demonstrate graph design, ontology alignment, and SPARQL
reasoning across a realistic domain — not to build a production data platform.
