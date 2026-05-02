# Lovable Prompt — Dev Practices Site

Paste the content below directly into Lovable as the initial prompt.

---

## PROMPT

Build a single-page portfolio site called **"Engineering Practices"**. This is a focused showcase of software development practices — testing, CI/CD, security, observability, and code quality — with links to real evidence in a GitHub repository. It is not a personal portfolio; there is no bio or contact section.

---

### Design

- **Dark mode by default** with a toggle to switch to light mode
- **Color palette:**
  - Dark background: `#1C1917` (warm stone-950)
  - Surface/card background: `#292524` (stone-800)
  - Primary accent: `#F59E0B` (amber-500) — used for headings, borders, highlights
  - Secondary text: `#A8A29E` (stone-400)
  - Body text: `#FAFAF9` (stone-50)
  - Light mode background: `#FAFAF9`, light mode surface: `#F5F5F4`
- **Style:** Minimal. Clean typography. No gradients, no hero images, no animations except subtle fade-in on scroll. Monospace font for code snippets.
- **Layout:** Single column, max-width 800px, centered. Sections separated by a subtle horizontal rule or spacing — no cards with heavy shadows.

---

### Structure

The page has the following sections in order:

#### 1. Header (sticky, minimal)
- Left: site title "Engineering Practices" in amber
- Right: dark/light toggle icon button
- No navigation links

#### 2. Hero
- Large heading: **"Engineering Practices"**
- Subheading: *"How I design, test, deploy, and observe production software — with evidence from real projects."*
- Small body text below: *"Each claim below links to the actual code, config, or commit that proves it."*
- GitHub link button (amber outline): "View Portfolio on GitHub → github.com/ahembal/portfolio"

---

#### 3. Section: Testing

Heading: **Testing**

Intro paragraph:
*"Tests are not a formality. They are the spec made executable. The choice of test type — unit, integration, load — is a design decision: what failure mode am I actually guarding against?"*

Three subsections with small amber labels:

**UNIT TESTS — logic in isolation**
Validate individual functions with controlled inputs. Used for preprocessing (tokenisation input/output shapes), label mapping correctness, edge cases (empty strings, very long inputs).
→ Evidence: `p4-nlp-deployment/tests/test_nlp_inference.py`

**INTEGRATION TESTS — real dependencies**
The most important category. Tests that pass against a SQLite mock but fail against real PostgreSQL are not useful. In p2, tests spin up a real `postgres:16-alpine` container via testcontainers. UUID types, CHECK constraints, and the asyncpg driver are all exercised exactly as in production.
→ Evidence: `p2-metadata-ingestion/tests/test_ingestion.py`

**WHY TESTCONTAINERS, NOT MOCKS**
A mocked database gives false confidence. The p2 test suite uses a real Postgres container with the same schema constraints. If the test fails, it's a real failure. If it passes, the DB layer actually works.
→ Evidence: `p2-metadata-ingestion/tests/conftest.py`

---

#### 4. Section: CI/CD

Heading: **CI/CD**

Intro paragraph:
*"A pipeline is a contract: every merge to main is linted, tested, built, and deployed — automatically, repeatably, with no manual steps. Humans approve changes; machines execute them."*

Show this pipeline as a visual flow diagram (simple boxes with arrows, amber accent):
```
Push to main
  → Lint (ruff)
  → Test (pytest + real Postgres)
  → Build API image  +  Build Worker image  (parallel)
  → Push to GHCR
  → Update values.yaml (full SHA tag)
  → ArgoCD detects drift → Deploy to cluster
```

Three key decisions (as a small list with amber bullets):

• **Two separate images from one Dockerfile** — API and worker have different entrypoints. A worker-only fix doesn't rebuild or restart the API.

• **Full SHA image tags** — `latest` is mutable and unauditable. Short SHAs don't exist in the registry. Full SHA is immutable and traceable to the exact commit.

• **GitOps via ArgoCD** — the cluster's desired state lives in git. `kubectl apply` by hand is not how deployments happen.

Evidence links:
→ `p2-metadata-ingestion/.github/workflows/p2-ci.yml`
→ `p1-pcam-deployment/.github/workflows/p1-ci.yml`

---

#### 5. Section: Security

Heading: **Security**

Intro paragraph:
*"Security decisions should be deliberate and traceable — not default settings left unchanged. Each choice below maps to a standard."*

Four items (small amber label + description):

**DISTROLESS CONTAINERS**
No shell, no package manager, no OS utilities in the final image. Attack surface is the application and its dependencies only.
Standard: NIST SP 800-190 — container runtime hardening.
→ `p1-pcam-deployment/Dockerfile`

**SEALED SECRETS**
Credentials are never stored in plain text. Encrypted with the cluster's public key via `kubeseal` — safe to commit to git. Only the in-cluster controller can decrypt.
Standard: ISO 27001:2022 A.10 (cryptography).
→ `p2-metadata-ingestion/k8s/seal-secrets.sh`

**NON-ROOT CONTAINERS**
All containers run as UID 1001. Kernel exploits require root to escalate — non-root containers contain the blast radius.
Standard: CIS Kubernetes Benchmark v1.9.
→ `p1-pcam-deployment/helm/pcam-inference/templates/deployment.yaml`

**LOCAL SECRET MANAGEMENT**
Credentials used in operations are stored encrypted with GPG via `pass`. Never written to plain text files, never committed to git.

---

#### 6. Section: Observability

Heading: **Observability**

Intro paragraph:
*"You cannot improve what you cannot measure. Observability is not an afterthought — it is specified before deployment, not added when something breaks."*

Show a simple 2-column table of metrics:

| Metric | Type | Why |
|--------|------|-----|
| `ingest_requests_total` | Counter | Throughput — rate() gives req/s |
| `ingest_request_latency_ms` | Histogram | p95 reveals tail latency invisible to averages |
| `ingest_queue_depth` | Gauge | Queue depth goes up and down — Counter is wrong type |
| `ingest_jobs_total` | Counter | Job completion rate by outcome |
| `ingest_job_duration_seconds` | Histogram | End-to-end worker processing time |

Body text below table:
*"The Grafana dashboard has 7 panels: ingest rate, queue depth, job completion rate, job duration p50/p95/p99, API latency p95, worker replicas (HPA), failed jobs. The queue depth gauge is queried from Redis `LLEN` at scrape time — no background polling loop needed."*

Evidence:
→ `p2-metadata-ingestion/monitoring/grafana-dashboard.yaml`
→ `p2-metadata-ingestion/src/api/main.py`

---

#### 7. Section: Code Quality

Heading: **Code Quality**

Intro paragraph:
*"Code quality is not aesthetic preference. It is operational necessity. Inconsistent formatting creates noise in diffs. Unsorted imports cause merge conflicts. Unused variables are hidden bugs."*

Three items:

**RUFF**
Single tool replacing flake8 + isort + black. Runs in CI on every push. Rules: E (style), F (pyflakes), I (import sort).
→ `p2-metadata-ingestion/pyproject.toml`

**PYDANTIC MODELS AS LIVING SCHEMA**
API contracts are defined as Pydantic models. The model *is* the documentation — it validates at runtime, generates OpenAPI automatically, and fails loudly on contract violations.
→ `p2-metadata-ingestion/src/api/schemas.py`

**DOCUMENTATION STANDARDS**
Every project has: `SPEC.md` (what and why), `PROGRESS.md` (decisions with timestamps), `docs/architecture.md`, `docs/design-decisions.md`, `docs/runbook.md`. An operations log records every manual cluster change with date, action, and rationale.
→ `runbooks/ops-log.md`

---

#### 8. Section: How it fits together

Heading: **How it fits together**

Full paragraph (render as a readable block of body text):

*"These practices are not independent checklists. They compose.*

*Tests make CI trustworthy — you can merge confidently because the pipeline ran against real dependencies. CI makes deployment safe — every artifact is traceable to a commit, tested, and built deterministically. Security makes deployment auditable — secrets are encrypted, containers are minimal, nothing runs as root. Observability makes production understandable — when something breaks (and it will), you have the metrics to know what broke, when, and why. Code quality makes all of the above maintainable — readable code is debuggable code, and documented decisions survive beyond the person who made them.*

*The through-line: reduce the cost of being wrong. Tests catch mistakes before deployment. Monitoring catches mistakes in production. Documentation ensures mistakes are not repeated."*

Add a final note in smaller secondary text:
*"Every cluster issue encountered during this portfolio is documented in `runbooks/known-issues.md` — with likelihood, impact, detection time, recovery time, and risk score (FMEA methodology). Including the ones that caused hours of debugging."*

---

#### 9. Footer

Minimal. One line:
`github.com/ahembal/portfolio`  |  Built with evidence, not claims.

---

### Technical requirements

- React + Tailwind CSS
- Dark/light mode toggle using a context or state, persisted to localStorage
- Evidence links open in a new tab pointing to `https://github.com/ahembal/portfolio/blob/main/<path>`
- Mobile responsive
- No external images or icon packs — use simple SVG icons inline if needed
- The pipeline flow diagram in the CI/CD section can be a simple flex layout with amber-colored boxes and right-arrows

---
