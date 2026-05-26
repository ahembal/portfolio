# Implementation Notes — P6 Research Agent
*Last updated: 2026-05-03*

This document describes how each part was built: what structure was chosen,
what problems were hit during development, and what decisions were made along
the way. It is developer-facing — for how the finished product works see
`how-it-works.md`, for design rationale see `q-agent-design.md`.

---

## Phase 1 — Tools

### src/tools/pubmed.py

Two functions: `search(query, max_results)` and `fetch(pmid)`.

`search` calls `Entrez.esearch` to get a list of PMIDs, then `Entrez.efetch`
to retrieve Medline records and parse titles. A 0.35s sleep is added between
requests to respect NCBI's rate limit (3 req/s unauthenticated).

`fetch` calls `Entrez.efetch` for a single PMID and parses the full Medline
record. Year is extracted from the `DP` (date published) field by splitting
on the first space.

Both functions catch all exceptions and return an error dict rather than
raising. This is required: if a tool raises, the LangGraph node raises, and
the entire agent crashes.

**Problem hit:** NCBI requires `Entrez.email` to be set before any API call.
This is set at module load time from the `NCBI_EMAIL` environment variable
(falls back to a placeholder). Without it, NCBI returns HTTP 400.

---

### src/tools/uniprot.py

One function: `lookup(query, organism)`.

Calls the UniProt REST search API (`/search?query=...&format=json`). The
query is constructed as `gene:{query} AND organism_name:{organism}` to narrow
results. The first result is returned.

Fields parsed: `primaryAccession`, `genes[0].geneName.value`, recommended
protein name, organism scientific name, sequence length, domain features
(type=Domain), disease comments (type=DISEASE), and function comment
(type=FUNCTION).

**Problem hit:** UniProt's JSON structure nests deeply. All field extractions
use `.get()` chains to avoid KeyError on incomplete records. Disease and
domain fields are lists — the code flattens them to plain string lists.

---

### src/tools/vector_store.py

Two functions: `index(documents, persist_dir)` and `search(query, k, persist_dir)`.

`index` splits each document's text into overlapping chunks (512 chars,
64 char overlap), assigns each chunk a stable ID based on
`hash(source:chunk_index:chunk_text[:64])`, and upserts into ChromaDB.
Using `upsert` (not `add`) means re-indexing the same document is safe —
existing chunks are overwritten, not duplicated.

`search` encodes the query with `sentence-transformers` (all-MiniLM-L6-v2)
and queries ChromaDB. Returns an empty list if the collection is empty rather
than letting ChromaDB raise.

**Problem hit:** ChromaDB raises if you query an empty collection. Added a
count check before querying — returns `[]` if count is 0.

**Problem hit:** Initial chunk IDs used only `source:chunk_index`. Two different
documents with chunks of the same index (0, 1, 2…) from the same source name
would collide. Fixed by adding the first 64 chars of chunk text to the hash.

---

### tests/test_tools.py

11 tests across three test classes: `TestPubmedSearch`, `TestPubmedFetch`,
`TestUniprotLookup`, `TestVectorStore`.

PubMed and UniProt tests mock all HTTP — `Entrez.esearch`, `Entrez.read`,
`Entrez.efetch`, `Medline.parse`, and `requests.get` are all patched.
`time.sleep` is also patched so tests run instantly.

Vector store tests use a real ChromaDB instance in `tmp_path` — no mocking.
This is intentional: the embedding pipeline (tokenise → encode → cosine
similarity) cannot be meaningfully mocked, and a mock would not catch the
most likely failure modes (model not loading, ChromaDB API changes).

**Problem hit:** `pytest-asyncio` was not needed here (all tools are
synchronous), but `pyproject.toml` needed `pythonpath = ["."]` so `src.*`
imports resolved correctly from the project root.

---

## Phase 3 — FastAPI + Streamlit

### src/api/schemas.py
Pydantic models: `QueryRequest`, `QueryResponse`, `Citation`, `StepRecord`,
`HealthResponse`. `Citation` has a `type` field ("pubmed" or "uniprot") so
the Streamlit UI can render the correct link format for each.

### src/api/main.py — /query/stream (SSE endpoint)

**What SSE is:** Server-Sent Events — the server holds an HTTP connection open
and pushes newline-delimited chunks to the client as they are ready. Each chunk
has the format `data: {json}\n\n`. The client reads them one by one. There is
no polling, no WebSocket handshake — it is plain HTTP.

**Why SSE over a blocking POST /query:**
`graph.invoke()` blocks the event loop for 40–90 seconds while Llama 3.1 8B
runs inference. The Streamlit UI shows a blank page for that entire duration.
SSE lets the UI show each tool call and result as it happens — the user sees
"Searching PubMed…" while the agent is still working.

**Event types emitted:**

| Type | Payload | When |
|------|---------|------|
| `tool_call` | `{tool, args}` | LLM decides to call a tool |
| `tool_result` | `{tool, content}` | Tool returns a result |
| `answer` | `{content}` | Final LLM answer (after all tools) |
| `citations` | `{citations: [...]}` | Extracted citations |
| `done` | — | Stream complete |
| `error` | `{message}` | Any exception or timeout |

**Implementation:** LangGraph's `graph.stream()` is synchronous (not async).
It cannot be awaited inside a FastAPI async handler. The solution:

1. A daemon thread runs `graph.stream()` and pushes each yielded event into an
   `asyncio.Queue` via `loop.call_soon_threadsafe(queue.put_nowait, event)`.
2. The async generator `generate()` awaits items from the queue with a 180s
   timeout and yields them as SSE lines.
3. FastAPI wraps the generator in a `StreamingResponse` with
   `media_type="text/event-stream"` and `X-Accel-Buffering: no` (required to
   prevent nginx from buffering the stream).

**Problem hit:** `asyncio.Queue` is not thread-safe to write to directly.
`queue.put_nowait(event)` from a thread can corrupt the queue.
Fix: use `loop.call_soon_threadsafe()` which schedules the put on the event
loop thread safely.

### src/api/main.py
lifespan pattern: `build_graph()` called once at startup, stored in `_state`.
Citation extraction happens in the `/query` handler by iterating over
`ToolMessage`s and parsing their JSON content — the agent itself does not
return structured citations, only the API layer does.

**Problem hit:** `_build_llm()` is called inside each LangGraph node rather
than once at module level, to avoid holding a persistent connection and to
allow easier mocking in tests.

Health check calls Ollama's `/api/tags` endpoint via `httpx` with a 3s timeout.
If Ollama is unreachable the response is "degraded", not an exception — the API
stays up and the health check is informational.

### streamlit/app.py
Calls `POST /query` with a 120s timeout — CPU inference on 3 tool calls takes
40–60s. The agent trace is in an `st.expander` so the answer is visible
immediately without scrolling past tool call output.

### docker-compose.yml
Four services: `api`, `streamlit`, `ollama`, `chromadb`. `api` depends on
`ollama` with `condition: service_healthy` — Ollama's healthcheck polls
`/api/tags` until the model server is ready. `chromadb` is included as a
standalone service for local dev; in K8s the API uses an embedded ChromaDB
PVC instead.

---

## Phase 4 — Helm + K8s + CI/CD

### helm/research-agent/
Three deployments: `research-agent-api`, `research-agent-streamlit`, `ollama`.
Ollama's deployment uses `nodeSelector: kubernetes.io/hostname: quick-thrush`
(64 GB RAM node) and a 10 Gi PVC (`ceph-rbd`) with `subPath: ollama` — the
`subPath` is required to avoid the Ceph RBD `lost+found` issue (ISS-006).
ChromaDB PVC also uses `subPath: chromadb` for the same reason.

### .github/workflows/p6-ci.yml
`test` → `build-api` + `build-streamlit` (parallel) → `update-tags`.
`update-tags` uses two `sed` passes to replace both `tag: latest` entries in
`values.yaml` with the full `$GITHUB_SHA`. The same full-SHA pattern as p2 —
GHCR uses the full digest as the authoritative reference.

### ArgoCD Application CR
Committed at `helm/research-agent/templates/argocd-application.yaml`.
Watches `p6-research-agent/helm/research-agent` on `main`, `CreateNamespace=true`.
Same pattern as p1 and p2 — no new ArgoCD infrastructure needed.

---

## Phase 2 — Agent tests (test_agent.py)

`_TOOLS` is a module-level dict in `graph.py`. Tests that need to mock a
specific tool replace `_TOOLS["tool_name"]` directly (not via `patch`) and
restore the original in a `finally` block. Patching the module-level import
name (`src.agent.graph.pubmed_search`) does not work because `act` dispatches
via `_TOOLS`, not via the name binding.

`pytest.mark.e2e` registered in `pyproject.toml`. E2E tests require Ollama
running locally with `llama3.1:8b` pulled — skipped in CI with
`pytest -m "not e2e"`.

---

## Phase 2 — Agent graph

### src/agent/prompts.py

Single constant `SYSTEM_PROMPT`. Five rules: always cite with structured
identifiers, admit uncertainty, use minimum tool calls, report errors
explicitly, keep answers concise.

No templating or dynamic content — the prompt is static. Variables like
the available tools are communicated via the tool schemas bound to the LLM,
not via the system prompt.

---

### src/agent/graph.py

LangGraph `StateGraph` with three nodes: `reason`, `act`, `respond`.

State type is `AgentState(TypedDict)` with a single field `messages` annotated
with `add_messages` — LangGraph's built-in reducer that appends rather than
replaces on each state update.

Tool schemas are defined as OpenAI-format JSON (`type: function`) and bound
to the LLM via `.bind_tools()`. This tells the LLM what tools are available
and what arguments they take — the LLM returns structured `tool_calls` in its
response when it wants to use a tool.

The `act` node iterates over all `tool_calls` in the last AIMessage and
executes each. Results are wrapped in `ToolMessage` with the matching
`tool_call_id` so LangChain can correlate them.

The router function `_router` checks whether the last message has `tool_calls`.
If yes → `act`. If no → `respond`. This is a conditional edge in LangGraph.

`respond` is a separate final node that calls the LLM one more time without
tools bound, forcing it to synthesise a plain text answer from all accumulated
context.

**Design decision:** `_build_llm()` is called inside each node rather than
once at module level. This avoids holding a persistent connection and makes
the graph easier to test with a mocked LLM.

---

## Post-Phase 2 fixes (2026-05-06)

### src/agent/prompts.py — system prompt revision

**Problem hit:** The original system prompt said "use the minimum number of
tool calls needed." Llama 3.1 8B interpreted this aggressively — after a
single `pubmed_search` returning 10 titles, it generated an answer without
calling `pubmed_fetch`. The answer cited real PMIDs but was based on titles
only, not actual abstracts.

**Fix:** Rule 2 now explicitly states that `pubmed_search` returns titles only
and `pubmed_fetch` must be called before citing a paper. Rule 3 was tightened
to prohibit citing any identifier not retrieved by a tool call.

The original "minimum tool calls" intent is preserved — the fix makes explicit
what "minimum" means: one search is not enough if you haven't read the content.

### src/tools/pubmed.py — English language filter

**Problem:** PubMed indexes papers from journals worldwide. Non-English
abstracts were being returned and the LLM could silently produce incorrect
summaries from them.

**Fix:** The query is wrapped with `AND English[Language]` before passing to
Entrez: `f"({query}) AND English[Language]"`. This is a standard PubMed
filter — the same syntax available in the PubMed web UI.

### src/api/main.py — citation provenance validation

**Problem:** The LLM hallucinated `[UniProt:P04641]` in an answer about TP53
without calling `uniprot_lookup`. P04641 is not the human TP53 accession
(P04637 is). The identifier was plausible but invented.

**Implementation:**
After the agent finishes, the API builds a set of retrieved identifiers from
the tool call history (all PMIDs from `pubmed_search`/`pubmed_fetch`, all
accessions from `uniprot_lookup`). It then extracts all `[PMID:xxxxx]` and
`[UniProt:Pxxxxx]` patterns from the answer text using regex, and subtracts
the retrieved set:

```python
retrieved_ids = {c.id for c in unique_citations}
cited_pmids   = set(re.findall(r'\[PMID:(\d+)\]', answer))
cited_uniprot = set(re.findall(r'\[UniProt:([A-Z0-9]+)\]', answer))
hallucinated  = (cited_pmids | cited_uniprot) - retrieved_ids
```

If `hallucinated` is non-empty, a warning is appended to the answer text.
The response is not blocked — the warning surfaces to the caller who can
decide how to handle it.

**What this does not catch:** claims that misrepresent a real retrieved paper,
title-only citations (PMID retrieved via search but abstract never fetched).
See `docs/answer-quality.md` for the full scope of what is and isn't validated.

### src/api/main.py — duplicate `answer = synth.content` removed

A duplicate line `answer = synth.content` was present after the synthesis
fallback block. No functional impact (the value was the same) but removed
for clarity.
