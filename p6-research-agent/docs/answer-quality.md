# Answer Quality — P6 Research Agent
*Last updated: 2026-05-06*

This document covers how answer quality is defined, what is validated
automatically, and where the honest limits of that validation are.

---

## The core quality problem

The agent's value proposition is that citations are grounded in retrieved data,
not generated from memory. This fails in two ways:

1. **Hallucinated citations** — the LLM generates a PMID or UniProt accession
   that was never retrieved. The identifier may be real (a valid PMID that
   exists in PubMed) but the LLM did not read the paper — it invented the
   association between the claim and the citation.

2. **Title-only grounding** — `pubmed_search` returns titles and PMIDs. If the
   LLM answers from titles without calling `pubmed_fetch`, citations are
   technically retrieved but the factual claims are based on titles only.
   A title can be misleading; an abstract is the actual source.

---

## What we validate automatically

### Citation provenance check

After the agent finishes, the API cross-references citations in the answer
against the tool call history:

- Every PMID cited in the answer must have been returned by `pubmed_search`
  or `pubmed_fetch` in this session
- Every UniProt accession cited must have been returned by `uniprot_lookup`

Citations that appear in the answer but not in the tool history are flagged.
This catches the most obvious hallucination: a PMID the agent invented.

**What it does not catch:**
- A real PMID cited in a context that misrepresents the paper
- A PMID that was searched but whose abstract contradicts the claim
- Title-only grounding (the PMID was retrieved via search but never fetched)

### Abstract fetch check

For each PMID cited in the answer, the validator checks whether `pubmed_fetch`
was called for that PMID in this session. If a PMID appears in the answer
but only via `pubmed_search` (not `pubmed_fetch`), a warning is added to the
response.

This does not block the answer — it surfaces the issue to the caller.

---

## What requires human judgement

Automated validation catches structural problems (wrong provenance, unfetched
citations). It cannot catch:

| Problem | Why automation fails |
|---------|---------------------|
| Factually wrong claim that matches the abstract | Would require reading comprehension, not just identifier matching |
| Correct PMID cited for the wrong reason | Requires understanding the paper's actual argument |
| Missing important context | No way to know what the LLM should have said |
| Appropriate uncertainty | Hard to judge when "I don't know" was the right answer |

This is why `docs/testing.md` uses qualitative e2e evaluation — a human reads
the output and judges whether it is correct. Automated metrics are a floor,
not a ceiling.

---

## Known failure: hallucinated UniProt accession

**Observed (2026-05-06):** The agent answered a query about TP53 in
glioblastoma with `[UniProt:P04641]` in the answer. No `uniprot_lookup` was
called in that session. P04641 is not the human TP53 accession (P04637 is).

**Root cause:** The LLM generated the citation from its training weights, not
from retrieval. It "knew" that TP53 has a UniProt accession and guessed one.

**Fix in progress:** Citation provenance check (above) will catch this. The
prompt engineering fix (see `q-agent-design.md`) reduces the likelihood of
early stopping that leads to the LLM falling back on memory.

---

## Production gap

The current implementation validates provenance (was this identifier retrieved?)
but not faithfulness (does the claim match what was retrieved?). Faithfulness
scoring requires an LLM-as-judge pipeline — this is planned for p7.

See `PRODUCTION-READINESS.md` for the full list of answer quality gaps.
