# How the Site Works — P5 Engineering Practices
*Last updated: 2026-05-03*

This document explains the purpose of the site — not the technical build,
but how it helps a reader understand the portfolio as a whole.

---

## What the site is for

The six portfolio projects (p1–p6) each solve a specific problem. Taken
individually, each looks like a competent technical exercise. Taken together,
they show a consistent set of engineering decisions made across different
domains, languages, and infrastructure layers.

The dev practices site makes that consistency visible.

A reviewer reading p1 sees distroless containers and Sealed Secrets. A reviewer
reading p2 sees the same patterns. Without the site, they might notice this. With
the site, they can verify it — with links to the actual files.

**The site's job:** connect the dots between projects so the reviewer does not
have to do that work themselves.

---

## How each section connects to the portfolio

### Testing

Shows that test strategy is not per-project ad hoc, but follows a consistent
philosophy: the right test type for the right failure mode.

- p1 tests validate image preprocessing and model output shape
- p2 tests use real Postgres (testcontainers) because mocked DB tests gave false confidence on a previous project
- p4 tests mock the model to test the inference pipeline without loading 268 MB of weights

The through-line: each test type is chosen for a reason, not because it was easy.

### CI/CD

Shows that the delivery pipeline is the same across p1, p2, and p4:
lint → test → build → push → update values.yaml → ArgoCD deploys.

The specific details differ (one image vs two, different test suites) but the
architecture is identical. This matters because it shows the pattern was
deliberately chosen and applied, not just copied once.

The site links to the actual CI workflow files — a reviewer can confirm this
is real, not a claim.

### Security

Shows that security decisions reference standards (NIST, ISO 27001, CIS) and
are applied consistently across projects — not just in p1 where the SPEC
mentioned compliance.

Distroless appears in p1, p2, p4. Sealed Secrets in p1 and p2. Non-root
containers everywhere. The site makes this cross-project consistency visible.

### Observability

Shows that metrics are designed before deployment — not added reactively when
something breaks. The choice of metric type (Counter vs Gauge vs Histogram) is
explained with the reasoning, not just listed.

Without this context, a reader seeing `ingest_queue_depth` as a Gauge might
not know that a Counter was considered and rejected (queues go down as well as up).
The site explains the decision.

### Code Quality

Shows that tooling choices are deliberate. Ruff replaced three separate tools
(flake8, isort, black). Pydantic models are not just validation — they are the
API contract made executable. Documentation has timestamps so staleness is
visible.

These are small decisions individually. Collectively they show an engineer who
thinks about maintainability, not just functionality.

### How it fits together

The synthesis section is the payoff. It answers the implicit question a
reviewer has after reading five separate sections: "okay but does this person
understand why these things matter together, not just how to use each tool?"

The answer in the site: they compose. Tests make CI trustworthy. CI makes
security auditable. Security makes observability meaningful. Each layer depends
on the ones below it.

---

## What the site does NOT do

- It does not explain the projects in detail — each project has its own docs
- It does not make claims that are not backed by evidence links
- It does not mention the specific job application context
- It does not have a bio or contact section

The site is narrow by design. A reviewer who wants depth goes to the project
repo. The site's job is to orient them — to show the pattern before they look
at the details.

---

## How to read the site alongside the portfolio

Suggested reading order for a reviewer:

1. **Site** — read the full page (~10 minutes). Understand the practices and where the evidence lives.
2. **p1 docs** — `security-compliance.md`, `q7-docker-helm-k8s.md`. Detailed treatment of security and deployment.
3. **p2 docs** — `architecture.md`, `design-decisions.md`. Most complete example of the async pipeline pattern.
4. **p3 docs** — `q8-hpc-narrative.md`. HPC experience with real benchmark numbers.
5. **p4 docs** — `how-it-works.md`, `training-design.md`. End-to-end ML: from dataset choice to production serving.
6. **p6** — the most complex project: LangGraph agent, RAG, Ollama, life science data.

The site is the map. The projects are the territory.
