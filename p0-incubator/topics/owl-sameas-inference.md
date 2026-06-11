# owl:sameAs + OWL Inference in Fuseki

**Status:** parked
**Target:** p9 — knowledge graph
**Opened:** 2026-05-21

## What it is

OWL (Web Ontology Language) inference allows a SPARQL endpoint to follow
`owl:sameAs` links between URIs at query time. If node A and node B are
declared `owl:sameAs`, an OWL-aware reasoner treats them as the same entity —
triples attached to either URI are reachable from both.

Apache Jena Fuseki supports OWL inference via an inference model configured
in `fuseki/config.ttl`. It is off by default.

## Why it matters for this portfolio

p9 originally used two URI spaces for paper nodes:
- `p9:paper_PMID` — our own triples (title, authors, p9:mentions)
- `purl.uniprot.org/pubmed/PMID` — UniProt's citation edges

An `owl:sameAs` triple bridged them. The design was semantically correct but
broke in practice: plain SPARQL cannot follow `owl:sameAs`, so multi-hop
queries that crossed the bridge (Q7 disease traversal, Q9 EDAM topics)
returned nothing.

The fix applied was pragmatic: paper nodes were moved to the UniProt pubmed
URI namespace directly, eliminating the bridge. But the alternative — enabling
OWL inference in Fuseki — is architecturally cleaner and preserves URI
ownership boundaries.

## Connections to existing projects

- **p9 — knowledge graph:** directly. The current state uses the pragmatic
  fix (single URI namespace). Revisiting this would mean re-introducing
  `p9:paper_*` URIs and enabling inference.

## Open questions

- [ ] What is the query performance impact of OWL inference at 130k+ triples?
      At 1M+ triples?
- [ ] Does enabling inference on the full dataset affect queries that do not
      use `owl:sameAs`? (Inference adds overhead to every query.)
- [ ] Is there a way to scope inference to only the paper subgraph, not the
      full dataset?
- [ ] Is URI ownership a real concern at this scale? Using UniProt's pubmed
      URIs for our own entities is pragmatic but breaks the linked-data
      principle that URI owners control the meaning of their identifiers.

## Evidence / research

**2026-05-21** — Q7 (disease traversal) and Q9 (EDAM topics) returned no
results. Root cause: SPARQL traversal could not cross the `owl:sameAs` bridge
between `p9:paper_PMID` and `purl.uniprot.org/pubmed/PMID`. Plain Fuseki does
not follow `owl:sameAs` by default.

**2026-05-21** — Fix applied: moved paper nodes to UniProt pubmed URI
namespace. Rationale: inference layer adds overhead to every query across the
whole dataset; the data-level fix is cheaper and permanent at current scale.

**2026-05-21** — Design decision documented in `docs/ontology-design.md` and
`TODO.local`.

## Decision

**Parked.**

Reason: the pragmatic fix (single URI namespace) is sufficient at current
scale (131k triples). The inference approach is architecturally cleaner but
adds query overhead and operational complexity.

Condition to revisit: dataset grows significantly (>1M triples), or URI
ownership becomes a concern (e.g. the portfolio is used in a context where
linked-data correctness is evaluated). In that case, re-introduce `p9:paper_*`
URIs and either enable OWL inference in `fuseki/config.ttl` or rewrite
queries to use `VALUES`/`UNION` to avoid the cross-namespace traversal.
