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

## How it was built

Built with **Lovable** (React + Tailwind). Dark by default with light mode toggle.
Warm amber color palette. Hosted on Vercel.

See `content.md` for all site content and `lovable-prompt.md` for the initial
Lovable prompt.
