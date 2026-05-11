# Service Level Agreement
*Portfolio homelab — internal SLA*
*Owner: Emre Balsever*

---

## What this is

A self-imposed SLA. The portfolio owner is both provider and customer. This document
defines what "acceptable service" means for each project, what constitutes a breach,
and what must happen when a breach occurs.

This mirrors how production engineering teams operate: SLOs are targets, the SLA is
the accountability mechanism, and the ops-log is the breach record.

---

## Objectives

Full SLO definitions with Prometheus queries are in `slos.yaml`. Summary:

| Service | Metric | Target | Window |
|---------|--------|--------|--------|
| p1 PCam inference | Availability | 99% | 30d |
| p1 PCam inference | p99 latency | < 2s | 30d |
| p2 Metadata ingestion | Pipeline success rate | 99% | 30d |
| p2 Metadata ingestion | p95 latency | < 30s | 30d |
| p4 NLP inference | Availability | 99% | 30d |
| p4 NLP inference | p95 latency | < 500ms | 30d |
| p6 Research agent | Availability | 95% | 30d |
| p6 Research agent | p95 latency | < 120s | 30d |

---

## Error budget

Each SLO has an error budget — the allowed failure headroom within the window.

| Service | SLO | Error budget (30d) |
|---------|-----|-------------------|
| p1 availability | 99% | 7.2 hours of downtime |
| p4 availability | 99% | 7.2 hours of downtime |
| p6 availability | 95% | 36 hours of downtime |

When the error budget is exhausted, reliability work takes priority over new features.

---

## What constitutes a breach

A breach occurs when an SLO is missed over the 30-day rolling window, OR when
a single incident causes more than 1 hour of complete unavailability for p1/p4,
or more than 4 hours for p6.

---

## Response commitments

| Severity | Definition | Response time | Resolution target |
|----------|-----------|---------------|-------------------|
| P1 | Service completely unavailable | Acknowledge within 1h | Resolve within 4h |
| P2 | SLO breached, service degraded | Acknowledge within 4h | Resolve within 24h |
| P3 | SLO at risk (>50% budget consumed) | Acknowledge within 24h | Plan within 1 week |

---

## Breach protocol

When a breach occurs:

1. **Document** in `runbooks/ops-log.md` — what failed, when, impact
2. **Root cause** — identify and document the cause
3. **Fix** — resolve the immediate issue
4. **Post-mortem** — what prevented detection, what prevents recurrence
5. **Update known-issues.md** if the root cause is a structural risk

---

## Exclusions

The following are not counted against SLOs:

- Planned maintenance (announced in ops-log before the window)
- Cluster node failures beyond single-node loss (sought-perch is already cordoned)
- External API unavailability (NCBI Entrez, UniProt, HuggingFace Hub)
- Dardel/UPPMAX HPC jobs (not a live service)
