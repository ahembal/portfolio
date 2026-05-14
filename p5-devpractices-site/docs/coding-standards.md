# Coding Standards
*Conventions applied consistently across all projects in this portfolio.*

---

## Type hints

All function signatures use Python type hints for parameters and return types.

```python
# correct
def lookup(query: str, organism: str = "human") -> dict:

# incorrect
def lookup(query, organism="human"):
```

For structured state and configuration, use `@dataclass` or `TypedDict`:

```python
@dataclass
class ServingConfig:
    bucket: str
    model_key: str
    device: str = "auto"

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]
```

Type hints serve as documentation and enable static analysis. They are not
optional — all new functions must be typed.

---

## Comments

Default is no comments. Add a comment only when the WHY is non-obvious:
- A hidden constraint
- A subtle invariant
- A workaround for a specific bug
- Behaviour that would surprise a reader

Never explain WHAT the code does — well-named identifiers do that.
Never reference the current task, fix, or caller — those belong in the commit message.

```python
# correct — explains a non-obvious constraint
time.sleep(REQUEST_DELAY)   # stays under NCBI 3 req/s rate limit

# incorrect — explains what the code obviously does
prob_tumour = float(probs[1])   # get tumour probability from index 1
```

---

## Error handling

External calls (APIs, databases, file I/O) return a dict with an `error` key on
failure — they never raise exceptions that escape to the caller.

```python
# correct
def fetch(pmid: str) -> dict:
    try:
        ...
        return {"pmid": pmid, "title": title, ...}
    except Exception as e:
        return {"error": str(e)}

# incorrect — exception escapes to caller
def fetch(pmid: str) -> dict:
    record = Entrez.efetch(...)   # raises on failure
    return parse(record)
```

The caller decides what to do with an error. This pattern is used consistently
across all tool functions in p6, all API endpoints in p1/p2/p4.

---

## Naming

- Functions: `snake_case`, verb-first (`load_model`, `build_graph`, `search`)
- Classes: `PascalCase` (`ServingConfig`, `AgentState`, `UniprotInput`)
- Constants: `UPPER_SNAKE_CASE` (`REQUEST_DELAY`, `EMBED_MODEL`)
- Files: `snake_case.py`

---

## No premature abstraction

Three similar lines is better than a premature abstraction. Don't create a helper
for two call sites. Don't design for hypothetical future requirements.

---

## Validation at boundaries

Validate inputs at system boundaries — user input, external API responses, LLM
outputs. Don't validate internal function calls between trusted code.

For LLM tool inputs, use Pydantic `@field_validator` with `mode="before"` to
coerce `None` to defaults and normalise strings before they reach the function body.
See `p6-research-agent/docs/tools.md` for the full pattern.

---

## Linting

All Python code is linted with `ruff --select E,F,I` before committing.
Run locally — never rely on CI to catch lint errors first.

---

## Structured logs

Every service must emit JSON-formatted logs. This is a mandatory contract —
not optional. Unstructured text logs cannot be queried across services.

### Required fields

Every log line must have these fields:

| Field | Type | Example |
|-------|------|---------|
| `timestamp` | ISO 8601 | `"2026-05-12T06:43:43Z"` |
| `level` | string | `"INFO"` |
| `service` | string | `"p1-pcam-inference"` |
| `message` | string | `"Model loaded"` |

Add context fields as needed — they make logs queryable:

```json
{"timestamp": "2026-05-12T06:43:43Z", "level": "INFO", "service": "p1-pcam-inference", "message": "Model loaded", "device": "cpu", "hub_id": "1aurent/resnet18.tiatoolbox-pcam"}
{"timestamp": "2026-05-12T06:43:55Z", "level": "INFO", "service": "p1-pcam-inference", "message": "Prediction complete", "label": "tumour", "confidence": 0.999, "latency_ms": 288.9}
{"timestamp": "2026-05-12T06:44:01Z", "level": "ERROR", "service": "p1-pcam-inference", "message": "Model load failed", "error": "Connection refused", "hub_id": "1aurent/resnet18.tiatoolbox-pcam"}
```

### Implementation

Use `python-json-logger` — the standard library for JSON logging in Python.

```python
import logging
from pythonjsonlogger import jsonlogger

def setup_logging(service: str) -> logging.Logger:
    logger = logging.getLogger(service)
    handler = logging.StreamHandler()
    formatter = jsonlogger.JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%SZ",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "service"},
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    return logger

log = setup_logging("p1-pcam-inference")
log.info("Model loaded", extra={"device": "cpu"})
log.error("Model load failed", extra={"error": str(e)})
```

### Log levels

| Level | When to use |
|-------|-------------|
| `DEBUG` | Detailed internal state — disabled in production |
| `INFO` | Normal lifecycle events — startup, shutdown, successful operations |
| `WARNING` | Unexpected but recoverable — fallback used, retry triggered |
| `ERROR` | Operation failed — request failed, external call failed |
| `CRITICAL` | Service cannot continue — use sparingly |

### What to log

**Always log:**
- Service startup with key config (model ID, device, endpoint)
- Service shutdown
- Each request — method, path, status, latency
- External API calls — target, outcome, latency
- Any `ERROR` or `WARNING` condition

**Never log:**
- Credentials, tokens, or secrets
- Full request/response bodies (may contain PII)
- Per-token inference details (too verbose)
