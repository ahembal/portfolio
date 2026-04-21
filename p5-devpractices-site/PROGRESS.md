# Project 5 — Dev Practices Site
## Progress Tracker
*Last updated: 2026-04-21*

---

## Steps

### Phase 1 — Site skeleton
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 1 | mkdocs.yml | ⬜ Todo | MkDocs config: site name, Material theme, nav structure, search plugin, git-revision-date plugin. Defines the shape of the site before writing content — catches structural issues early rather than after all pages are written. |
| 2 | docs/index.md | ⬜ Todo | Landing page: what the portfolio is, who it's for, links to each project. First thing a reviewer sees. Sets context so they know what to look for and where to go. |
| 3 | requirements.txt | ⬜ Todo | mkdocs, mkdocs-material, mkdocs-git-revision-date-localized-plugin — pinned. Reproducible build means the CI deploy produces the same output as local serve, always. |
| 4 | Dockerfile | ⬜ Todo | Multi-stage: build with `mkdocs build`, serve static output with nginx. Consistent with other projects' container pattern; lets the site run on the homelab cluster if needed. |
| 5 | Local mkdocs serve test | ⬜ Todo | Verify the site renders before writing content. A broken nav config or missing theme plugin fails silently — one `mkdocs serve` confirms everything wires up. |

### Phase 2 — Content pages
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 6 | docs/testing.md | ⬜ Todo | Testing strategy across p1–p4: unit tests (logic in isolation), integration tests (real deps), load tests (Locust). Explains what each type catches and why. Links to actual test files as evidence — not abstract claims. |
| 7 | docs/ci-cd.md | ⬜ Todo | GitHub Actions pipeline walkthrough: lint → test → build → push → tag values.yaml. Then how ArgoCD picks up from where CI ends: detects drift, reconciles cluster state to git. The full loop in one place. |
| 8 | docs/security.md | ⬜ Todo | Security decisions with standard citations: distroless (NIST SP 800-190), Sealed Secrets (ISO 27001 A.10), RBAC least privilege (CIS K8s Benchmark 5.1.5), non-root UID 65532. Links to p1/docs/security-compliance.md for the full compliance mapping. |
| 9 | docs/observability.md | ⬜ Todo | What to observe and why: request rate (Counter), latency percentiles (Histogram, histogram_quantile), HPA replica count, pod CPU. Explains the difference between service health (what Prometheus measures) and model health (what it doesn't — acknowledged gap). |
| 10 | docs/code-quality.md | ⬜ Todo | Tooling: Ruff (lint + format, replaces flake8+black+isort), pre-commit hooks (local gate before CI), Pydantic models (type safety at API boundaries). Each tool chosen for a specific reason, not cargo-culted. Links to pyproject.toml. |

### Phase 3 — Q10 doc + deployment
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 11 | docs/q10-dev-practices.md | ⬜ Todo | The Q10 answer. Synthesises testing, CI/CD, security, observability, code quality into a coherent narrative — how they interact and reinforce each other, not five isolated topics. References the evidence pages rather than repeating them. |
| 12 | GitHub Actions deploy to GitHub Pages | ⬜ Todo | `mkdocs gh-deploy` on push to main. The site's own CI/CD pipeline is itself an example of the practices it documents — the medium reinforces the message. Zero additional infra needed (GitHub Pages is free). |
| 13 | Update root README | ⬜ Todo | Add link to the live GitHub Pages site. README is often the first thing a reviewer opens — if the site exists but isn't linked, it effectively doesn't exist. |

---

## Quick status

```
Phase 1  [░░░░░] 0/5  ← start here
Phase 2  [░░░░░] 0/5
Phase 3  [░░░]   0/3
```
