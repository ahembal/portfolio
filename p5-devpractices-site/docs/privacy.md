# Privacy — Telemetry Opt-Out

All services in this portfolio run with telemetry disabled. This is a
non-negotiable baseline, not an optional hardening step.

---

## Why this matters

Many open-source tools enable telemetry by default — usage statistics, error
reports, and anonymised identifiers are sent to the vendor's servers without
explicit consent. This is an opt-out model: data leaves your infrastructure
unless you actively stop it.

In a biomedical research context this is unacceptable:
- Queries may reference patient-adjacent data (disease names, gene variants,
  clinical trial identifiers)
- Research questions themselves can be sensitive intellectual property
- GDPR requires a lawful basis for any data transfer outside the EU — "it was
  the default" is not a lawful basis
- Software that phones home introduces an uncontrolled external dependency

The standard across this portfolio: **all telemetry is disabled at deploy time**,
documented here, and verified for every new dependency added.

---

## Telemetry status by component

| Component | Used in | Default | Disabled via | Status |
|-----------|---------|---------|--------------|--------|
| ChromaDB | p6, p7 | Opt-out | `ANONYMIZED_TELEMETRY=False` | ✅ Disabled |
| Streamlit | p6, p7 | Opt-out | `STREAMLIT_BROWSER_GATHER_USAGE_STATS=false` | ✅ Disabled |
| Grafana | monitoring | Opt-out | `GF_ANALYTICS_REPORTING_ENABLED=false` | ✅ Disabled |
| HuggingFace Hub | p1, p4, p8 | Opt-out | `HF_HUB_DISABLE_TELEMETRY=1` | ✅ Disabled |
| LangChain | p6 | Opt-out (LangSmith) | No API key set — tracing inactive | ✅ Inactive |
| Ollama | p6 | None | N/A | ✅ No telemetry |
| Apache Jena Fuseki | p9 | None | N/A | ✅ No telemetry |
| FastAPI / Uvicorn | p1, p2, p4, p6 | None | N/A | ✅ No telemetry |
| rdflib | p9 | None | N/A | ✅ No telemetry |
| Celery | p2 | None | N/A | ✅ No telemetry |
| PostgreSQL | p2 | None | N/A | ✅ No telemetry |
| Redis | p2 | None | N/A | ✅ No telemetry |

---

## Where each is set

### ChromaDB — p6 research-agent

Set in the API pod's environment via ConfigMap:
```yaml
env:
  - name: ANONYMIZED_TELEMETRY
    value: "False"
```

### Streamlit — p6 research-agent

Set in the Streamlit pod's environment:
```yaml
env:
  - name: STREAMLIT_BROWSER_GATHER_USAGE_STATS
    value: "false"
```

### Grafana — monitoring namespace

Set in the Grafana Helm values:
```yaml
grafana.ini:
  analytics:
    reporting_enabled: false
    check_for_updates: false
```

### HuggingFace Hub — p1, p4, p8

Set in any pod that downloads models from HuggingFace Hub:
```yaml
env:
  - name: HF_HUB_DISABLE_TELEMETRY
    value: "1"
```

---

## Checklist for adding a new dependency

Before adding any new third-party library or service:

1. Check if it has telemetry (search docs for "telemetry", "analytics", "reporting", "usage stats")
2. If yes — find the opt-out mechanism (env var, config flag, config file)
3. Add it to the table above
4. Apply the opt-out in the relevant Helm chart or ConfigMap before deploying

When in doubt, assume opt-out and disable it.
