# Observability
*p11 — AI Developer Browser*

---

## Log format

All backend logs are emitted as single-line JSON to stdout, using the same
`JsonFormatter` convention as p6:

```json
{
  "timestamp": "2026-05-30T10:15:42.123Z",
  "level": "INFO",
  "logger": "ai-browser.agent",
  "message": "tool_invoked",
  "service.name": "ai-browser-backend",
  "tool": "fetch_page_text",
  "tool_args": "https://docs.python.org/3/library/asyncio.html"
}
```

Fields passed via `extra={}` in log calls are merged into the top-level JSON
object. This is OpenTelemetry-compatible — `service.name` and `environment`
align with OTel resource attributes.

---

## Log events

### Backend API (`src/api/main.py`)

| Event | Level | Key fields |
|-------|-------|------------|
| `chat_started` | INFO | `companion`, `page_url` |
| `chat_failed` | ERROR | `exception_type`, `exception_message` |
| `chat_completed` | INFO | `companion`, `latency_ms`, `tool_steps` |
| `research_proxied` | INFO | `question` (first 80 chars) |

### Agent graph (`src/agent/graph.py`)

| Event | Level | Key fields |
|-------|-------|------------|
| `tool_invoked` | INFO | `tool`, `tool_args` |
| `tool_error` | WARNING | `tool`, `error` |
| `tool_exception` | ERROR | `tool`, `exception_type`, `exception_message` |

Tool errors are returned as dicts, not exceptions — the agent continues with
degraded information. A `tool_error` WARNING means the companion received an
error result from the tool and may have given a partial answer.

---

## Prometheus metrics

Exposed at `GET /metrics`. The pod has `prometheus.io/scrape: "true"` annotation
so the existing cluster Prometheus picks it up automatically — no scrape config
change needed.

| Metric | Type | What it measures |
|--------|------|-----------------|
| `chat_total` | Counter | Total companion chat requests received |
| `chat_errors_total` | Counter | Requests that returned an error event |
| `chat_latency_seconds` | Histogram | End-to-end latency (buckets: 1, 5, 10, 30, 60 s) |

Latency buckets match p6's — inference on llama3.1:8b takes 10–60 s depending
on context length and number of tool calls.

The research companion's latency is dominated by p6 — requests that proxy to
p6 are counted here but the timer covers the full round trip including p6's
inference time.

---

## Health endpoint

`GET /health` checks two dependencies with a 3 s timeout each:

```json
{
  "status": "ok",
  "backend": "ok",
  "p6_research_agent": "ok",
  "ollama": "ok"
}
```

| Field | Degraded condition |
|-------|--------------------|
| `p6_research_agent` | p6 API unreachable or returns non-200 |
| `ollama` | Ollama `/api/tags` unreachable or returns non-200 |
| `status` | Either dependency not `"ok"` |

The backend stays up even when dependencies are degraded — the health response
is informational. The Kubernetes readinessProbe calls `/health` every 10 s;
if p6 or Ollama is down, the pod is removed from the Service endpoints and
traffic stops routing to it.

---

## Reading logs in production

```bash
# Stream all backend logs
kubectl logs -f -n ai-browser -l app=ai-browser-backend

# Filter to tool errors
kubectl logs -n ai-browser -l app=ai-browser-backend \
  | grep '"message": "tool_error"'

# Check recent health
kubectl logs -n ai-browser -l app=ai-browser-backend --since=10m \
  | grep '"message": "chat_completed"'
```
