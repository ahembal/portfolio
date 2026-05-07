# How the Research Agent Works — P6
*Last updated: 2026-05-03*

This document explains every part of the p6 research agent — what each
component does, how data flows through the system, how the agent reasons,
and where the limitations are.

---

## The problem this solves

A researcher asks: *"What is known about TP53 mutations in glioblastoma?"*

Answering this properly requires:
1. Searching PubMed for recent papers on the topic
2. Looking up TP53 in UniProt to get the canonical protein record
3. Synthesising the results into a coherent answer with citations

No single API call does all of this. A single fine-tuned model would hallucinate
citations. The solution is an agent — a loop where an LLM decides what to look
up, calls the appropriate tools, observes the results, and decides whether it
has enough to answer.

---

## The big picture

```
Researcher types a question
        │
        ▼
Streamlit UI
        │  POST /query {"question": "What is known about TP53 in glioblastoma?"}
        ▼
FastAPI
        │  passes question to LangGraph agent
        ▼
LangGraph agent loop (runs until answer is ready):
        │
        ├─ Reason: LLM reads question + history → decides which tool to call
        │
        ├─ Act: tool is called, result added to agent state
        │   ├── pubmed_search("TP53 glioblastoma") → [PMID:123, PMID:456, ...]
        │   ├── pubmed_fetch(PMID:123) → abstract + metadata
        │   ├── uniprot_lookup("TP53") → protein record (domains, disease)
        │   └── rag_search("TP53 mutations") → relevant local corpus chunks
        │
        └─ Respond: LLM generates final answer when it has enough context
        │
        ▼
FastAPI response:
{
  "answer": "TP53 is mutated in ~30% of glioblastoma cases...",
  "citations": [{"pmid": "12345678", "title": "...", "url": "..."}],
  "steps": [{"tool": "pubmed_search", "input": "...", "output": "..."}]
}
        │
        ▼
Streamlit shows answer + collapsible agent trace
```

---

## Components

### 1. The LLM — Llama 3.1 8B via Ollama

**What it does:** The reasoning engine. Given the question and the accumulated
tool results, it decides what to do next (call a tool or answer) and eventually
generates the final answer.

**Why Llama 3.1 8B:**
- Runs on the homelab cluster (CPU inference, ~10 seconds per query)
- No API key, no cost, no data leaving the network
- 8B parameters fits in ~16 GB RAM — within the cluster's capacity
- Can be swapped for GPT-4o or Claude by changing one config value

**What Ollama is:**
Ollama is a local model server — similar to running a small version of the
OpenAI API on your own machine. You `ollama pull llama3.1:8b` once (~4 GB
download), then the model is available at `http://localhost:11434`. The agent
calls it via LangChain's Ollama integration exactly like it would call any
other LLM.

**Limitations:**
- CPU inference: ~10 seconds per LLM call. A multi-step query with 3 tool calls
  takes ~40-60 seconds total. Acceptable for research assistant use, not for
  real-time applications.
- 8B parameters is a small model. It can reason and synthesise but will make
  mistakes on complex multi-hop questions that larger models handle better.
- Context window: 128k tokens. Long tool outputs (many PubMed abstracts) can
  exceed this — the agent truncates old results to stay within limits.

---

### 2. LangGraph — the agent loop

**What it does:** Manages the agent's control flow — what happens in what order,
what state is passed between steps, when to stop.

**Why LangGraph and not plain LangChain:**
Plain LangChain hides the agent loop inside a ReAct string parser — you can't
see or modify the individual steps. LangGraph makes the loop explicit as a
directed graph. You can visualise it, add nodes, and test individual steps
without running the full loop.

**The three node types:**

```
┌─────────┐     tool call decided      ┌─────┐     tool result      ┌──────┐
│  REASON  │ ─────────────────────────► │ ACT │ ──────────────────► │      │
│  (LLM)   │ ◄────────────────────────  │     │                     │      │
└─────────┘     loop continues          └─────┘                     │      │
     │                                                                │      │
     │  answer decided                                                │      │
     ▼                                                                │      │
┌──────────┐                                                          │      │
│ RESPOND  │ ◄────────────────────────────────────────────────────── │      │
│  (LLM)   │                                                          │      │
└──────────┘                                                          └──────┘
```

**State** is passed between all nodes. It accumulates:
- The original question
- All tool calls made so far (name, input, output)
- The full conversation history

Every node receives the full state, so the LLM always has complete context.

**How the agent decides to stop:**
After each Reason step, the LLM either outputs a tool call (JSON with tool name
and arguments) or a plain text answer. If it outputs plain text, the loop exits
and Respond generates the final formatted answer.

---

### 3. Tools

Tools are the agent's hands — they fetch real information from external sources.
The LLM cannot access the internet itself; it can only reason about what the
tools return.

#### Tool 1: pubmed_search

**Purpose:** Search PubMed for papers matching a query. Returns a list of PMIDs
(PubMed IDs) and titles.

**API used:** NCBI Entrez (via Biopython)
**Rate limit:** 3 requests/second without API key, 10/second with key
**Authentication:** none required for public access

**Input:**
```python
pubmed_search(query="TP53 glioblastoma mutations 2023", max_results=5)
```

**Output:**
```json
[
  {"pmid": "37891234", "title": "TP53 mutation landscape in GBM..."},
  {"pmid": "37654321", "title": "Targeting mutant p53 in glioblastoma..."}
]
```

**Limitations:**
- Returns titles and PMIDs only — not full abstracts. The agent must call
  `pubmed_fetch` to get the content.
- Results are sorted by relevance (NCBI's ranking) — not by date or citation count.
- PubMed indexes papers from journals worldwide. Results may include non-English abstracts — the LLM has no language filter and may silently produce an incorrect summary if the fetched abstract is not in English.

---

#### Tool 2: pubmed_fetch

**Purpose:** Fetch the full abstract and metadata for a specific paper by PMID.

**Input:**
```python
pubmed_fetch(pmid="37891234")
```

**Output:**
```json
{
  "pmid": "37891234",
  "title": "TP53 mutation landscape in GBM...",
  "abstract": "Background: TP53 mutations occur in approximately...",
  "authors": ["Smith J", "Jones A"],
  "journal": "Nature Cancer",
  "year": 2023,
  "url": "https://pubmed.ncbi.nlm.nih.gov/37891234/"
}
```

**Why citations are important here:**
The PMID and URL are stable, persistent identifiers. When the agent cites
`[PMID:37891234]`, a researcher can verify the source immediately. This is
possible because PubMed is FAIR — every record has a stable, resolvable identifier.

---

#### Tool 3: uniprot_lookup

**Purpose:** Look up a protein by gene symbol, protein name, or UniProt accession.
Returns the canonical record: sequence length, domains, disease associations,
organism.

**API used:** UniProt REST API (`https://rest.uniprot.org`)
**Authentication:** none required

**Input:**
```python
uniprot_lookup(query="TP53", organism="human")
```

**Output:**
```json
{
  "accession": "P04637",
  "gene": "TP53",
  "protein_name": "Cellular tumor antigen p53",
  "organism": "Homo sapiens",
  "length": 393,
  "domains": ["p53 tetramerisation domain", "DNA-binding domain"],
  "diseases": ["Li-Fraumeni syndrome", "various cancers"],
  "url": "https://www.uniprot.org/uniprot/P04637"
}
```

**Why UniProt accessions matter:**
`P04637` is a permanent, species-specific identifier for human TP53. Unlike a
gene symbol (which can be ambiguous across species or databases), the UniProt
accession is unambiguous and stable. The FAIR data properties of UniProt are
what make this citation trustworthy.

---

#### Tool 4: rag_search

**Purpose:** Search a local document corpus for relevant context. Used when
PubMed and UniProt don't have enough information, or when domain-specific
background is needed.

**What the corpus contains:**
- SciLifeLab platform and infrastructure descriptions
- Seed PubMed abstracts on key topics (pre-indexed at startup)
- Any documents added by the user

**How it works:**
```
Query: "TP53 mutations"
        │
        ▼  sentence-transformers encodes query → embedding vector
        ▼  ChromaDB finds k=5 nearest neighbours in vector space
        ▼  returns top-k text chunks with similarity scores
        │
        ▼
[{"text": "TP53 is the most frequently mutated gene in human cancers...",
  "source": "seed_abstracts.txt", "score": 0.87}]
```

**Why RAG and not just more PubMed searches?**
The vector store gives the agent access to pre-curated, context-specific
documents that may not surface easily in a PubMed keyword search. For example,
a detailed description of SciLifeLab's genomics infrastructure is not on PubMed.

**Limitations:**
- Quality depends on what was indexed. An empty corpus returns nothing useful.
- Similarity search is semantic (meaning-based) not keyword-based — a very
  specific query may match unexpected documents.
- ChromaDB persists to disk on a PVC. If the PVC is lost, the corpus must be
  rebuilt.

---

### 4. FastAPI — the serving layer

**Endpoint: POST /query**

**Purpose:** Accept a research question, run the agent, return the answer.

**Request:**
```json
{
  "question": "What is known about TP53 mutations in glioblastoma?",
  "max_steps": 10
}
```

**Response:**
```json
{
  "answer": "TP53 is mutated in approximately 30% of glioblastoma cases...\n\nSources: [PMID:37891234], [UniProt:P04637]",
  "citations": [
    {"pmid": "37891234", "title": "TP53 mutation landscape in GBM", "url": "https://pubmed.ncbi.nlm.nih.gov/37891234/"},
    {"accession": "P04637", "gene": "TP53", "url": "https://www.uniprot.org/uniprot/P04637"}
  ],
  "steps": [
    {"step": 1, "tool": "pubmed_search", "input": "TP53 glioblastoma 2023", "output": "[{pmid:...}]"},
    {"step": 2, "tool": "uniprot_lookup", "input": "TP53 human", "output": "{accession:P04637...}"},
    {"step": 3, "tool": "pubmed_fetch", "input": "37891234", "output": "{abstract:...}"}
  ],
  "latency_ms": 42300
}
```

**Why `steps` is in the response:**
Transparency. A researcher can see exactly which tools were called, in what
order, and what they returned. This is what separates the agent from a black-box
chatbot — the reasoning process is visible and verifiable.

**`max_steps`:**
Safety parameter. If the agent hasn't produced an answer after `max_steps` tool
calls, it is forced to respond with what it has. Prevents infinite loops on
ambiguous questions.

**Limitations:**
- Latency: ~40-60 seconds for a typical 3-step query on CPU inference
- No streaming in v1 — the client waits for the full response. Streaming is a
  future improvement.
- One question at a time per container — no request queuing

---

**Endpoint: GET /health**

Checks Ollama is reachable and the vector store is initialised.

```json
{"status": "ok", "ollama": "ok", "vector_store": "ok", "model": "llama3.1:8b"}
```

---

### 5. Streamlit — the demo UI

**What it shows:**
- Text input for the research question
- The final answer formatted with citations as clickable links
- An expandable "Agent trace" section showing each tool call step-by-step

**Why show the trace:**
The trace is what makes this different from ChatGPT. A researcher can see
"the agent searched PubMed for X, found papers Y and Z, then looked up protein P
in UniProt" — and verify each source. Without the trace, the answer is
unverifiable.

---

## Limitations summary

| Limitation | Impact | Note |
|-----------|--------|------|
| CPU inference (~10s/LLM call) | 40-60s per query | Acceptable for research use, not real-time |
| 8B parameter model | Reasoning errors on complex queries | Swap to larger model via config |
| No streaming | Client waits for full response | Future improvement |
| RAG quality depends on corpus | Poor results if corpus is thin | Pre-index relevant documents at startup |
| PubMed rate limit (3 req/s) | Slow for many fetch calls | Use API key for 10 req/s |
| Non-deterministic | Same question may produce different tool order | LLM temperature controls this |
| Uncalibrated confidence | No certainty scores on citations | LLM admits uncertainty in prompt |

---

## CI/CD pipeline

```
git push to main (p6-research-agent/** changed)
        │
        ▼
GitHub Actions — test
  ruff check src/ tests/
  pytest tests/ -m "not e2e"   ← unit tests only, no Ollama needed
        │ passes
        ▼
GitHub Actions — build-api + build-streamlit (parallel)
  docker build -f Dockerfile      → ghcr.io/ahembal/research-agent-api:<full-SHA>
  docker build -f Dockerfile.streamlit → ghcr.io/ahembal/research-agent-streamlit:<full-SHA>
        │
        ▼
GitHub Actions — update-tags
  sed values.yaml → new SHA (both images)
  git pull --rebase && git push
        │
        ▼
ArgoCD detects drift → helm upgrade research-agent
  api + streamlit rolling update
  Ollama unchanged (upstream image, no rebuild)
```

**Key points:**
- E2E tests (require Ollama) are excluded from CI with `-m "not e2e"` — run manually before K8s deployment
- Two images built in parallel (api and streamlit) because they have different dependencies and change at different rates
- Ollama uses the upstream `ollama/ollama:latest` image — never rebuilt in CI
- Both GHCR packages (`research-agent-api`, `research-agent-streamlit`) need the `portfolio` repo added under "Manage Actions access" with **Write** permission before the first CI push — see p1 `deployment-troubleshooting.md §15` for the procedure
