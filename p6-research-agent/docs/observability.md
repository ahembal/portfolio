# Observability
*p6 — Research Agent*

---

## Why observability matters here

An LLM agent is a black box by default. Without structured logs you cannot
answer basic operational questions:

- Which tool failed and what was the error?
- How long did a query take end-to-end vs per-tool?
- Did the model hallucinate citations on this request?
- Is Ollama reachable right now?

p6 is instrumented at two layers — the API boundary and the agent graph
internals — so every request is fully traceable from HTTP entry to final answer.

---

## Log format

All logs are emitted as single-line JSON to stdout. Each line contains:

```json
{
  "timestamp": "2026-05-26T03:46:07.915Z",
  "level": "INFO",
  "logger": "p6-research-agent.graph",
  "message": "tool_invoked",
  "service.name": "p6-research-agent",
  "environment": "production",
  "tool": "pubmed_search",
  "tool_args": "BRCA1 cancer"
}
```

The format is OpenTelemetry-compatible — the `service.name` and `environment`
fields align with OTel resource attributes, making it straightforward to ship
to any log aggregator (Loki, OpenSearch, Datadog) without transformation.

The `JsonFormatter` in `src/api/logging_config.py` handles serialisation.
It merges any fields passed via `extra={}` into the top-level JSON object,
so domain-specific context sits alongside the standard fields rather than
being buried in a nested `extra` key.

---

## Two logging layers

### Layer 1 — API (`src/api/main.py`)

Covers the full request lifecycle.

| Event | Level | Key fields |
|-------|-------|------------|
| `service_starting` | INFO | `ollama_url`, `model` |
| `service_ready` | INFO | — |
| `query_started` | INFO | `question` (first 100 chars) |
| `query_failed` | ERROR | `exception_type`, `exception_message` |
| `provenance_warning` | WARNING | `hallucinated_ids` |
| `query_completed` | INFO | `latency_ms`, `tool_steps`, `citations`, `hallucinated` |
| `service_stopping` | INFO | — |

The `provenance_warning` event is particularly important: it fires when the
model cites an identifier (PMID, UniProt accession) that was not retrieved by
any tool call. This is the hallucination detection signal — a log aggregator
alert on `provenance_warning` with `hallucinated > 0` catches cases where the
model is inventing sources.

### Layer 2 — Agent graph (`src/agent/graph.py`)

Covers every tool call inside the ReAct loop. This layer is what makes the
agent's internal reasoning traceable.

| Event | Level | Key fields |
|-------|-------|------------|
| `tool_invoked` | INFO | `tool`, `tool_args` |
| `tool_error` | WARNING | `tool`, `error` |
| `tool_exception` | ERROR | `tool`, `exception_type`, `exception_message` |
| `tool_unknown` | WARNING | `tool` |

**Why tool-level logging matters:** tool errors are returned as
`{"error": "..."}` dicts rather than exceptions — this prevents a single tool
failure from crashing the agent loop. But without logging, these errors are
invisible unless you read the full API response. A `tool_error` WARNING means
the agent received an error result and may have continued with degraded
information; a `tool_exception` ERROR means the tool threw an exception that
was caught and wrapped.

---

## Prometheus metrics

In addition to logs, the API exposes metrics at `/metrics`:

| Metric | Type | What it measures |
|--------|------|-----------------|
| `query_total` | Counter | Total queries received |
| `query_errors_total` | Counter | Queries that returned HTTP 500 |
| `query_latency_seconds` | Histogram | End-to-end query latency (buckets: 1, 5, 10, 30, 60, 120 s) |

Latency buckets are intentionally coarse — Ollama inference on an 8B model
takes 40–90 s on a single GPU. The p50 bucket is 30 s; outliers above 60 s
indicate model cold start or resource contention.

---

## Health endpoint

`GET /health` returns structured status for each dependency:

```json
{
  "status": "ok",
  "ollama": "ok",
  "vector_store": "ok",
  "model": "llama3.1:8b"
}
```

`ollama` degrades to `"degraded"` or `"unreachable"` if the Ollama API
does not respond within 3 seconds. `vector_store` degrades if ChromaDB
raises on a test search. Overall `status` is `"degraded"` if either
dependency is not `"ok"`.

---

## Reading logs in production

```bash
# Stream all logs from the running pod
kubectl logs -f -n research-agent -l app=research-agent

# Filter to tool errors only
kubectl logs -n research-agent -l app=research-agent \
  | grep '"message": "tool_error"'

# Count hallucination warnings in the last hour
kubectl logs -n research-agent -l app=research-agent --since=1h \
  | grep '"message": "provenance_warning"' | wc -l
```

---

## Design decisions

**Why stdout, not a file?**
Kubernetes captures stdout/stderr and makes it available via `kubectl logs`.
Writing to a file inside a container requires volume mounts and rotation
policies. Stdout is zero-config and works with every log shipper.

**Why JSON, not plain text?**
Plain text requires regex parsing to extract fields. JSON is machine-readable
by default — any log aggregator can index `tool`, `latency_ms`, or
`hallucinated` as structured fields without configuration.

**Why two loggers (`p6-research-agent` and `p6-research-agent.graph`)?**
The graph logger is a child of the API logger in Python's logging hierarchy,
so it inherits the `JsonFormatter` automatically when `setup_logging()` is
called at startup. The separate name makes it easy to filter graph-layer
events from API-layer events in a log query.
