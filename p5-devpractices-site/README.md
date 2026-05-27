# P5 — Engineering Practices

A focused single-page site showcasing software engineering practices:
testing, CI/CD, security, observability, and code quality — with evidence
from real projects.

Live site: `[deployed URL — added after Vercel deployment]`

## What it covers

- **Testing** — unit tests, integration tests with real Postgres (testcontainers)
- **CI/CD** — GitHub Actions pipelines, full SHA image tags, GitOps via ArgoCD
- **Security** — distroless containers, SealedSecrets, non-root containers
- **Observability** — Prometheus metrics, Grafana dashboards
- **Code quality** — Ruff, Pydantic models, documentation standards
- **Synthesis** — how these practices compose and reinforce each other

Every claim links to actual code, config, or commits in the portfolio repo.

## Docs

| File | What it covers |
|------|----------------|
| [q10-dev-practices.md](docs/q10-dev-practices.md) | Full synthesis — testing, CI/CD, security, observability, code quality |
| [observability.md](docs/observability.md) | Prometheus metric types, what each project exposes |
| [coding-standards.md](docs/coding-standards.md) | Ruff, Pydantic, type hints, documentation standards |
| [gitops-image-updates.md](docs/gitops-image-updates.md) | How CI pushes images and ArgoCD picks them up |
| [conventional-commits.md](docs/conventional-commits.md) | Commit message format used across the repo |
| [privacy.md](docs/privacy.md) | GDPR considerations, data handling |

## How it was built

Built with **Lovable** (React + Tailwind). Dark by default with light mode toggle.
Warm amber color palette. Hosted on Vercel.

See `content.md` for all site content and `lovable-prompt.md` for the initial
Lovable prompt.
