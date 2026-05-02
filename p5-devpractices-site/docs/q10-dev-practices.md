# Engineering Practices — Synthesis
*Last updated: 2026-05-02*

## How it fits together

These practices are not independent checklists. They compose.

Tests make CI trustworthy — you can merge confidently because the pipeline ran
against real dependencies. CI makes deployment safe — every artifact is traceable
to a commit, tested, and built deterministically. Security makes deployment
auditable — secrets are encrypted, containers are minimal, nothing runs as root.
Observability makes production understandable — when something breaks (and it will),
you have the metrics to know what broke, when, and why. Code quality makes all of
the above maintainable — readable code is debuggable code, and documented decisions
survive beyond the person who made them.

The through-line: **reduce the cost of being wrong.**
- Tests catch mistakes before deployment
- Monitoring catches mistakes in production
- Documentation ensures mistakes are not repeated

## Evidence

| Practice | Key evidence |
|----------|-------------|
| Testing (testcontainers) | `p2-metadata-ingestion/tests/conftest.py` |
| CI/CD (full pipeline) | `.github/workflows/p2-ci.yml` |
| Security (distroless) | `p1-pcam-deployment/Dockerfile` |
| Security (SealedSecrets) | `p2-metadata-ingestion/k8s/seal-secrets.sh` |
| Observability (metrics) | `p2-metadata-ingestion/monitoring/grafana-dashboard.yaml` |
| Code quality (ruff) | `p2-metadata-ingestion/pyproject.toml` |
| Documentation (ops log) | `runbooks/ops-log.md` |
| Known issues register | `runbooks/known-issues.md` |
