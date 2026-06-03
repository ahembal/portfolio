# p14 — Knowledge Engineering
*Spec written: 2026-06-03*

---

## What

A maintained, versioned knowledge layer covering two connected domains:

1. **Biomedical domain** — proteins, pathology, diseases, tissues, experimental assays (aligned with EDAM, OBI, GO, DO)
2. **ML/AI layer** — models, tasks, datasets, metrics, experiments (aligned with MLSchema, schema.org, FAIR4ML)

The two layers are connected: a pathology classification task links to the tissue type it targets; a model links to the disease it is trained to detect.

This is shared infrastructure. Other projects consume it rather than each defining their own terms. The ontology is the tool; the goal is a living, queryable, consumable knowledge layer that evolves as the portfolio grows.

---

## Why

Every project in this portfolio touches some part of this vocabulary:

- p6 retrieves papers about proteins and diseases — but "protein" and "disease" are not defined consistently
- p7 evaluates retrieval quality — but the evaluation criteria implicitly assume domain concepts
- p8 tags models by task and format — but "task" is a free-text string with no shared definition
- p9 builds a knowledge graph — but its ontology coverage is shallow and not reusable outside p9
- p10 trains a pathology model — but the dataset, task, and tissue type are not linked to any shared vocabulary

Without a shared knowledge layer, every project reinvents its own terms. With it, the portfolio becomes a coherent system where concepts mean the same thing everywhere.

---

## What it produces

| Artifact | Description |
|----------|-------------|
| OWL ontology files | Machine-readable schema, versioned in git |
| Knowledge base | Instances, relationships, and inference rules built on top of the schema |
| SPARQL endpoint | Queryable via Apache Jena Fuseki (reuses p9 infrastructure) |
| Python client | Thin wrapper for downstream projects to look up terms, validate labels, resolve IRIs |
| Alignment map | Explicit mappings between the biomedical and ML layers (`owl:equivalentClass`, `skos:exactMatch`) |
| Changelog | Human-readable record of additions, deprecations, breaking changes |

---

## How downstream projects consume it

- **p6** — resolves entity types before retrieval; grounds tool output against defined terms
- **p7** — evaluation criteria reference defined concepts rather than free-text labels
- **p8** — model metadata (task, dataset, modality) uses shared IRIs instead of strings
- **p9** — imports this knowledge layer rather than defining its own; p9 becomes a graph over p14's vocabulary
- **p10** — training metadata (tissue type, stain, task) linked to defined terms at dataset creation time

---

## Key decisions to make

- Which upper ontology to align to (BFO vs DOLCE vs none)
- Depth of coverage — broad shallow map vs narrow deep map for pathology + ML
- Versioning strategy — OWL versioning, semver, or date-based
- Hosting — Fuseki pod on the cluster, or static files served from git
- Python client interface — term lookup only, or validation + inference

---

## What this is not

- Not a knowledge graph (that is p9) — this is the vocabulary and knowledge base p9 and others build on
- Not a data pipeline — no ingestion, no workers, no queues
- Not tied to a single downstream project — if it is only useful for one project, it failed

---

## Status

⬜ Not started
