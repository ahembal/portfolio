# n8n — Self-Hosted Workflow Automation

**Status:** raw
**Target:** new project (standalone) or p5 (as orchestration pattern doc)
**Opened:** 2026-05-21

## What it is

n8n is a self-hostable workflow automation platform (similar to Zapier or
Make, but open source and deployable on-premises). It provides a visual
node-based editor for connecting APIs, databases, and services into automated
workflows — without writing code for each integration.

The key differentiator from orchestration tools like Prefect or Airflow: n8n
is designed for human-in-the-loop processes and cross-system automation, not
batch data pipelines. A workflow might: receive a webhook from a form
submission → look up a record in a database → send an approval request via
email → wait for a response → trigger a downstream action.

## Why it matters for this portfolio

The portfolio demonstrates technical depth but is light on process automation
and human-in-the-loop workflows — which are highly relevant to research
infrastructure (grant approval workflows, data access request pipelines,
committee review chains).

In the Euro-BioImaging context specifically: data sharing agreements (DSAs)
involve multi-step approval workflows across institutions. n8n running on the
homelab could prototype that process in a way that complements the SPE/EHDS
framing.

## Connections to existing projects

- **p5 — dev practices:** the distinction between workflow automation (n8n)
  and pipeline orchestration (Prefect) is a real architectural choice that
  belongs in a "how we approach automation" doc in p5.
- **p9 — knowledge graph / SPE framing:** a DSA approval workflow is the
  governance layer that the homelab SPE is missing. n8n could implement the
  human-in-the-loop part of that governance layer.

## Open questions

- [ ] Is there a real use case in the portfolio that justifies n8n, or is
      this a tool looking for a problem?
- [ ] How does n8n differ from Prefect in practice for this portfolio's needs?
      (Prefect: data pipeline scheduling and retry logic. n8n: cross-system
      integration and human approval steps.)
- [ ] Is self-hosting n8n on the homelab operationally realistic given the
      cluster's current stability (sought-perch ISS-009 unresolved)?

## Evidence / research

**2026-05-21** — Noted in TODO.local as a future project. Context: shows
human-in-the-loop process automation relevant to research infrastructure.

## Decision

<!-- Pending. -->
