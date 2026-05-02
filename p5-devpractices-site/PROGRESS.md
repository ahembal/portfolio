# Project 5 — Dev Practices Site
## Progress Tracker
*Last updated: 2026-04-28*

---

## Cluster constraints
> **p5 does NOT deploy to the homelab cluster.**
- Deployed via GitHub Pages (`mkdocs gh-deploy`) — no K8s involvement
- No pull secrets, no namespaces, no Helm charts needed
- The Dockerfile is optional (for local preview only)

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

---

## Design change — 2026-05-02

**Previous approach:** MkDocs + Material theme + GitHub Pages (static docs site).

**Revised approach:** Lovable (React) + Vercel hosting.

**Why changed:**
MkDocs produces documentation-style output (ReadTheDocs look). A modern interactive
React site makes a stronger first impression. Lovable allows building a polished,
branded single-page site without context-switching from the rest of the portfolio work.

**What stays the same:** All content (testing, CI/CD, security, observability, code
quality, synthesis) is unchanged. Evidence links point to the same repo files.
The site is still strictly dev practices — no personal bio.

**New steps added below:**

### Phase 4 — Lovable build (new, replaces Phase 1-3 delivery)
| # | Step | Status | What & Why |
|---|------|--------|------------|
| 14 | content.md | ✅ Done | All site content written: 6 sections with evidence links, Q10 synthesis. Source of truth for what goes into Lovable. |
| 15 | lovable-prompt.md | ✅ Done | Full Lovable prompt: design spec (dark/amber, minimal), complete site structure, all copy, technical requirements (React + Tailwind, dark/light toggle, mobile responsive). |
| 16 | docs/q10-dev-practices.md | ⬜ Todo | Standalone Q10 answer doc — synthesises all sections into a narrative. |
| 17 | README.md | ⬜ Todo | Project readme explaining what the site is and how it was built. |
| 18 | Build in Lovable | ⬜ Todo | Paste lovable-prompt.md into Lovable, iterate until design matches spec. |
| 19 | Deploy to Vercel | ⬜ Todo | Connect Lovable output to Vercel for hosting. |
| 20 | Link from CV site | ⬜ Todo | Add link to the deployed site from the existing CV webpage. |

```
Phase 4  [██░░░░░] 2/7  ← in progress
```
