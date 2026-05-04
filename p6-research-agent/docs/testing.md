# Testing — P6 Research Agent
*Last updated: 2026-05-03*

All external API calls (PubMed, UniProt) are mocked — tests run without
network access. The vector store tests use a temporary directory so they
don't affect the real corpus.

---

## Test tiers

Tests are split into two tiers:

**Unit tests** (run in CI on every push):
```bash
pytest tests/ -v -m "not e2e"
```
No external dependencies. PubMed and UniProt calls are mocked. ChromaDB uses a temporary directory. The agent graph routing tests replace tool functions with `MagicMock`. These tests run in seconds on any machine without Ollama or network access.

**E2E tests** (run manually against a real deployment):
```bash
pytest tests/ -v -m e2e
```
Marked with `@pytest.mark.e2e`. Require Ollama running locally with `llama3.1:8b` pulled. Call the real agent loop end-to-end — LLM reasoning, tool dispatch, citation extraction. Run these before deploying to K8s to confirm the full system works, not on every commit.

This split is standard practice: unit tests gate every push (fast, deterministic), E2E tests gate deployments (slow, require live infrastructure). Running E2E tests in CI would make every push take minutes and fail whenever Ollama is unavailable.

---

## Agent graph (test_agent.py)

### test_router_goes_to_act_when_tool_calls_present
**Type:** Unit | **What it catches:** Router correctly identifies a pending tool call

Builds an AIMessage with a `tool_calls` list. Checks `_router` returns `"act"`.
If the conditional edge logic breaks, the graph would skip tool execution.

### test_router_goes_to_end_when_no_tool_calls
**Type:** Unit | **What it catches:** Router correctly identifies a finished reasoning step

Builds an AIMessage with plain text content and no tool calls. Checks `_router`
returns `END`. Without this, the agent would loop forever even after the
LLM produces its final answer.

### test_act_node_calls_pubmed_search
**Type:** Unit | **What it catches:** `act` node dispatches to the correct tool with correct arguments

Replaces `_TOOLS["pubmed_search"]` with a MagicMock. Checks the mock was called
with the exact arguments from the tool call, and that a ToolMessage with the
matching `tool_call_id` is returned. Patching `_TOOLS` directly (not the module
import) is required because `act` dispatches via the dict, not via the import name.

### test_act_node_handles_unknown_tool_gracefully
**Type:** Unit | **What it catches:** Unknown tool names return an error dict rather than raising

Passes a tool call with a name not in `_TOOLS`. Checks the returned ToolMessage
contains `{"error": "unknown tool: ..."}`. Without this, an LLM hallucinating a
tool name would crash the entire agent.

### test_act_node_calls_uniprot_lookup
**Type:** Unit | **What it catches:** `act` node dispatches to uniprot_lookup correctly

Same pattern as the pubmed_search test — confirms the dispatch mechanism works
for a second tool and that `tool_call_id` is correctly threaded through.

---

## PubMed tools

### test_returns_list_of_pmid_title
**Type:** Unit | **What it catches:** Parser correctly extracts PMID and title from Medline format

Mocks the NCBI Entrez API to return one record. Checks the output is a list
with the correct `pmid` and `title` keys. If the Medline parsing logic breaks,
this test fails.

### test_returns_empty_list_when_no_results
**Type:** Unit | **What it catches:** Correct handling of a valid but empty search result

Mocks NCBI returning an empty `IdList`. Checks the function returns `[]`
rather than crashing or returning `None`. Important because empty results
are common for niche queries.

### test_returns_error_dict_on_exception
**Type:** Unit | **What it catches:** Network errors don't crash the agent

Mocks NCBI throwing a network exception. Checks the function returns
`[{"error": "..."}]` rather than propagating the exception. The agent
must always get a dict back — if a tool crashes, the agent crashes too.

### test_returns_full_record
**Type:** Unit | **What it catches:** Fetch extracts all fields correctly

Mocks a full Medline record. Checks that `year` is extracted from the
`DP` (date published) field, `url` contains the correct PMID, and all
expected keys are present.

### test_returns_error_on_empty_record
**Type:** Unit | **What it catches:** Graceful handling when a PMID has no data

Mocks Medline returning an empty list. Checks the function returns an
error dict rather than crashing with an IndexError.

---

## UniProt tool

### test_returns_accession_and_gene
**Type:** Unit | **What it catches:** Correct JSON parsing of UniProt REST response

Mocks the UniProt REST API response. Checks that `accession`, `gene`,
`length`, and `url` are correctly extracted. If UniProt changes its JSON
structure, this test catches it.

### test_returns_error_when_not_found
**Type:** Unit | **What it catches:** Graceful handling of unknown genes

Mocks UniProt returning zero results. Checks the function returns
`{"error": "..."}` rather than crashing with a KeyError or IndexError.

### test_returns_error_on_network_failure
**Type:** Unit | **What it catches:** Network timeouts don't crash the agent

Mocks `requests.get` raising a `RequestException`. Checks the error is
caught and returned as a dict. Same reason as PubMed — the agent must
always receive a dict from every tool.

---

## Vector store

### test_index_and_search
**Type:** Integration (uses real ChromaDB + real model, no network)

Indexes two documents into a temporary ChromaDB instance. Searches for
"tumour suppressor" and checks:
- At least one result is returned
- The top result is about TP53, not SciLifeLab (semantic relevance check)
- Each result has `text`, `source`, and `score` keys

This is the most important vector store test — it confirms the full
embedding + retrieval pipeline works end-to-end.

### test_search_empty_corpus_returns_empty
**Type:** Unit | **What it catches:** Querying before indexing returns `[]` not an error

Creates a fresh empty ChromaDB. Checks that searching it returns an empty
list. Without this check, an empty corpus could throw a ChromaDB error that
crashes the agent on first startup.

### test_index_deduplicates_on_reindex
**Type:** Unit | **What it catches:** Re-indexing the same document doesn't duplicate it

Indexes the same document twice. Checks the chunk count is identical both
times — `upsert` should overwrite, not append. Without this, re-indexing
at startup would inflate the corpus and degrade search quality.
