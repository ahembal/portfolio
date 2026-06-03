# Portfolio Goal
*Reference this before starting any new project, feature, or doc.*

---

## The goal

Demonstrate end-to-end ML engineering capability across the full stack — training, serving, data pipelines, scale, agents, and evaluation — running on real infrastructure with production-grade CI/CD, security, and observability.

Not a collection of notebooks. Not a single-layer demo. The whole thing, connected.

---

## What the portfolio must prove

Each row is a capability that must be covered. If it is not covered, the portfolio is incomplete. If it is covered twice, one of those is scope creep.

| Capability | Proof | Covered by |
|------------|-------|------------|
| Model training | Train a model end-to-end, not just download a checkpoint | p1, p4, p10 |
| Model serving | Serve a model via a production API on real infrastructure | p1, p4 |
| Async data pipeline | Handle file ingestion, queuing, storage at production patterns | p2 |
| Scale | Benchmark compute at real HPC scale, not just local | p3 |
| LLM agents | Build a multi-tool agent grounded in real external data | p6 |
| Retrieval & evaluation | Evaluate a RAG system with rigorous methodology | p7 |
| Knowledge graphs | Represent structured knowledge, query it with SPARQL | p9 |
| Model packaging & registry | Track provenance, package for deployment, benchmark formats | p8 |
| Knowledge engineering | Build and maintain a living knowledge layer as shared semantic infrastructure; downstream projects consume it rather than each defining their own terms | p14 |
| Production infrastructure | CI/CD, GitOps, security, observability, consistent across projects | p5 + cross-cutting |

---

## Drift checks

Ask these before starting anything new.

**Scope creep**
- Does this add a proof point not already in the table above?
- If not — is it deepening an existing one, or is it just interesting?
- Interesting is not enough. Skip it.

**Depth vs breadth**
- Are all proof points covered to a demonstrable level before going deeper on any one?
- A half-finished project covers nothing. Finish before adding.

**Goal clarity**
- Does this work make the portfolio easier or harder to understand as a whole?
- If a visitor has 10 minutes, does this help or distract?

**Priority**
- What is the weakest proof point right now?
- Work on that first.

---

## Current weakest proof points

Update this section whenever the status changes.

| Capability | Status | What's missing |
|------------|--------|---------------|
| Model serving | 🔄 p4 incomplete | FastAPI + Helm for DistilBERT not built |
| Scale | 🔄 p3 incomplete | GPU benchmark results pending from Dardel |
| Retrieval & evaluation | 🔄 p7 in progress | Evaluation pipeline not finalised |
| Model packaging & registry | 🔄 p8 in progress | Registry integration with p10 not done |
| Model training | 🔄 p10 in progress | BEETLE Grand Challenge submission pending |
| Knowledge engineering | ⬜ p14 not started | Everything — spec written, no implementation yet |
