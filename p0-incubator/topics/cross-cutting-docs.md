# Cross-Cutting Documentation (Option C)

**Status:** raw
**Target:** repo root `docs/` — new files: scalability.md, security.md, observability.md
**Opened:** 2026-06-11

## What it is

Three narrative documents at the portfolio root that synthesise patterns
across all projects, rather than documenting each project in isolation.

- **scalability.md** — how data volume is handled from p2 (metadata
  ingestion) through p3 (Spark benchmark) through p9 (131k triples), and
  what was learned at each scale point.
- **security.md** — how secrets, credentials, network boundaries, and
  storage encryption are handled consistently across projects. What the
  homelab's security posture is and where the gaps are.
- **observability.md** — what is currently monitored, how, and what is
  not monitored but should be. Connects p8 (inference latency), p9
  (SPARQL query times), and the planned p11 evaluation framework.

## Why it matters for this portfolio

Per-project docs answer "what did you build?" Cross-cutting docs answer
"how do you think about systems?" The latter is what distinguishes a
portfolio from a collection of homework assignments.

A recruiter or hiring manager reading the root README can follow a link to
"how we handle security across all projects" and get a coherent answer
rather than having to read nine separate security sections.

## Connections to existing projects

Every project contributes at least one data point to each doc. The docs
are synthesis, not new work — the raw material already exists in per-project
docs, PROGRESS.md files, and TODO.local.

Notable inputs:
- **security.md:** p9 `docs/security.md` (most complete), homelab Tailscale
  + Ceph encryption, SPE/EHDS and EDPB safeguard requirements.
- **scalability.md:** p3 Spark results, p9 131k triples + TDB2 file lock
  rationale, p10 WSI tile extraction at 20×.
- **observability.md:** p8 latency benchmarks, p9 SPARQL query times,
  TODO.local ISS-009 (kube-proxy failure with no alerting).

## Open questions

- [ ] Is this worth doing before per-project READMEs are complete? The
      cross-cutting docs link back to per-project content — if that content
      does not exist yet, the narrative has nothing to point to.
- [ ] Which of the three docs has the most material ready today?
      Security is probably the strongest candidate to write first.
- [ ] Should these live at `docs/scalability.md` (repo root docs/) or
      inside p5-devpractices-site/ as part of the dev practices narrative?

## Evidence / research

**2026-06-11** — Listed as Option C in TODO.local. No further exploration
done. Noted as good for portfolio story-telling.

## Decision

<!-- Pending. Write after per-project READMEs are complete — the READMEs
     are the foundation these docs synthesise. -->
