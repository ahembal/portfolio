# P5 — Dev Practices Site — Spec

> Last updated: 2026-04-21

## What this project is

A static documentation site that consolidates everything this portfolio demonstrates
about software development practice — not as a list of bullet points, but as a
living document with links to real evidence in the repo.

**Portfolio question answered:** Q10 — Development practices: testing, CI/CD, code
quality, documentation, security, observability, and how these fit together in a
real project.

**Why a site and not just a markdown doc?**
A static site is itself a demonstration of the practices it describes: it has a build
pipeline (MkDocs → GitHub Pages), a Dockerfile, automated deployment, and version
control. The medium reinforces the message. It also gives reviewers a navigable,
readable reference rather than a wall of text.

---

## Stack

| Component | Choice | Why |
|-----------|--------|-----|
| Static site generator | MkDocs + Material theme | Simple, markdown-native, excellent search, widely used in engineering docs |
| Hosting | GitHub Pages (via GitHub Actions) | Zero infra overhead; deploys on every push to main; free |
| Local dev | `mkdocs serve` or Docker | One command, hot reload |
| Dockerfile | Serves via `mkdocs serve` or nginx | Lets it run on the homelab cluster if needed (consistent with other projects) |

---

## Site structure

```
docs/
  index.md              — Overview: what the portfolio is, what Q10 asks
  testing.md            — Testing strategy across p1–p4: unit, integration, contract
  ci-cd.md              — GitHub Actions pipelines, ArgoCD GitOps, what each stage does
  security.md           — Distroless, Sealed Secrets, RBAC, compliance mapping (links to p1)
  observability.md      — Prometheus, Grafana, structured logging, what to monitor and why
  code-quality.md       — Ruff, pre-commit hooks, type hints, review process
  q10-dev-practices.md  — The actual Q10 answer: synthesises the above into a narrative
```

Each page links to specific files and commits in the portfolio repo as evidence —
not abstract claims.

---

## Critical path

```
mkdocs.yml + docs/index.md (skeleton renders)
  → fill content pages (testing, ci-cd, security, observability, code-quality)
    → q10 synthesis doc
      → GitHub Actions deploy to GitHub Pages
        → Dockerfile for local/homelab serve
```

---

## Phase 1 — Site skeleton

| # | Task | Why |
|---|------|-----|
| 1 | `mkdocs.yml` | MkDocs configuration: site name, theme (Material), nav structure, plugins (search, git-revision-date). Defines the shape of the site before any content is written. |
| 2 | `docs/index.md` | Landing page: what the portfolio is, who it's for, links to each project. First thing a reviewer sees — sets context and navigation. |
| 3 | `requirements.txt` | `mkdocs`, `mkdocs-material`, `mkdocs-git-revision-date-localized-plugin`. Pinned so the build is reproducible. |
| 4 | `Dockerfile` | Multi-stage: build with `mkdocs build`, serve with nginx. Consistent with the rest of the portfolio's container pattern. |
| 5 | Local `mkdocs serve` test | Verify the site renders before writing content. Catches nav config errors and theme issues early. |

**Done when:** `mkdocs serve` starts with no errors and the index page renders in a browser.

---

## Phase 2 — Content pages

Each page is evidence-driven: claim → link to the actual file/commit that proves it.

| # | Task | Why |
|---|------|-----|
| 6 | `docs/testing.md` | Testing strategy across all projects: what types of tests exist (unit, integration, load), what they cover, where mocks are used vs. real dependencies, and why. Links to p1/test_inference.py, p2/test_ingestion.py, p4/test_nlp_inference.py. |
| 7 | `docs/ci-cd.md` | GitHub Actions pipeline walkthrough: what each job does (lint → test → build → push → deploy), why jobs are ordered that way, how ArgoCD picks up from where CI leaves off. Includes the GitOps flow diagram from p1's Q7 doc. |
| 8 | `docs/security.md` | Security decisions with standard citations: distroless images (NIST SP 800-190), Sealed Secrets (ISO 27001 A.10), RBAC least privilege (CIS K8s Benchmark), non-root containers. Links to p1/docs/security-compliance.md for the full mapping. |
| 9 | `docs/observability.md` | What to observe and why: request rate, error rate, latency percentiles (p50/p95/p99), HPA replica count, pod CPU. Why Prometheus counters vs histograms, what histogram_quantile does. Links to p1's Grafana dashboard config. |
| 10 | `docs/code-quality.md` | Tooling: Ruff (lint + format), pre-commit hooks, type hints (Pydantic models as living schema), docstring conventions. Why these tools and not others. Links to pyproject.toml. |

---

## Phase 3 — Q10 doc + deployment

| # | Task | Why |
|---|------|-----|
| 11 | `docs/q10-dev-practices.md` | The Q10 answer: synthesises testing, CI/CD, security, observability, code quality into a coherent narrative about how they fit together. References the concrete evidence from the other pages rather than making abstract claims. |
| 12 | GitHub Actions deploy to GitHub Pages | `mkdocs gh-deploy` on push to main. The site's own deployment is an example of CI/CD — the medium reinforces the message. |
| 13 | Update portfolio root README | Link to the live GitHub Pages site. The README is often the first thing a reviewer opens. |

---

## Acceptance criteria (project complete)

- [ ] `mkdocs serve` runs locally with no errors
- [ ] All content pages written with links to real repo evidence (no abstract claims)
- [ ] `docs/q10-dev-practices.md` written — answers Q10 in full
- [ ] Site deployed to GitHub Pages via GitHub Actions
- [ ] Root README links to the live site
