# Agent Design Rationale — P6 Research Agent
*Last updated: 2026-05-03*

---

## Why an agent, not a fine-tuned model?

A fine-tuned model produces answers from its training weights — it cannot look up a paper published last week, and it cannot retrieve the canonical UniProt accession for a protein it learned about at training time. It also hallucinate citations: it will confidently produce a PMID that does not exist.

An agent does not answer from memory. It reasons about what information it needs, calls tools to retrieve it, observes the results, and produces an answer grounded in real data. Every citation is a real identifier the agent retrieved — not one it generated.

The cost is latency. A 3-step agent query on CPU inference takes 40–60 seconds. For a research assistant used to analyse a single topic at a time, this is acceptable.

---

## Why LangGraph over plain ReAct?

Plain LangChain ReAct hides the agent loop inside a string parser: the LLM produces a text string with "Thought / Action / Observation" structure, and the framework parses it. This is fragile — the loop breaks if the LLM deviates from the format — and opaque: you cannot see or intercept individual steps.

LangGraph makes the loop explicit as a directed graph with named nodes and typed state. Benefits:

- **Inspectable**: the graph can be visualised and every node can be tested in isolation
- **Debuggable**: state is a typed dict; every tool call and its result are recorded
- **Extensible**: adding a new node (e.g. a web search tool) is a one-line graph change, not a prompt rewrite
- **Controllable**: the recursion limit prevents infinite loops without embedding a counter in the prompt

---

## Tool design decisions

**Why Biopython Entrez for PubMed?**
Biopython is the standard NCBI client in the Python ecosystem. It handles rate limiting (3 req/s without API key) and Medline XML/text parsing. The alternative — direct HTTP to NCBI — would require reimplementing both.

**Why UniProt REST and not other protein databases?**
UniProt is the authoritative, curated source for protein annotations. Accessions are stable and species-specific — P04637 is always human TP53. Gene symbols (e.g. "TP53") are ambiguous across species; UniProt accessions are not. This stability is what makes citations trustworthy.

**Why ChromaDB for the vector store?**
ChromaDB runs embedded (no separate server process) — simpler to deploy locally and in K8s. The sentence-transformers model (all-MiniLM-L6-v2) is small enough for CPU inference and well-suited for scientific text similarity. Both can be swapped without changing the tool interface.

**Why RAG in addition to PubMed/UniProt?**
PubMed search is keyword-based and returns papers, not structured background knowledge. The vector store gives the agent access to pre-curated context that would not surface in a keyword search — for example, descriptions of SciLifeLab infrastructure, or background summaries written specifically for this domain.

---

## RAG corpus curation

The corpus is seeded at startup with domain-specific background documents. PubMed abstracts retrieved during a session can optionally be indexed for reuse in follow-up questions (not implemented in v1 — noted as future work).

Parameters chosen empirically via `notebooks/rag_exploration.ipynb`:

| Parameter | Value | Reason |
|-----------|-------|--------|
| chunk_size | 512 chars | Balances precision and context for abstract-length text |
| overlap | 64 chars | Prevents semantic loss at chunk boundaries |
| k | 5 | Enough context without saturating the LLM prompt |
| model | all-MiniLM-L6-v2 | Small, fast, effective for scientific text similarity |

---

## Evaluation methodology and its limits

The agent is evaluated on 5 fixed test questions (see `tests/test_agent.py`) by checking:

1. The right tools were called (pubmed_search for literature questions, uniprot_lookup for protein questions)
2. Citations are real, resolvable identifiers — PMIDs that exist in PubMed, accessions that exist in UniProt
3. The answer is consistent with the retrieved content — it does not contradict what the tools returned

There is no automatic quality metric for answer quality. A BLEU score or accuracy number would not capture whether an answer is scientifically correct, well-cited, or appropriately uncertain. Qualitative evaluation by a domain expert is the right methodology. It is more honest to say this than to report a number that appears objective but is not.

The 5 test questions cover: a gene-disease association, a protein structure question, a treatment mechanism question, a multi-hop reasoning question, and a question where the answer is genuinely uncertain.

---

## FAIR data infrastructure and citation quality

The agent's citation reliability depends directly on PubMed and UniProt being FAIR — Findable, Accessible, Interoperable, Reusable.

Concretely:
- **Stable identifiers**: PMIDs and UniProt accessions do not change. A citation from 2005 is still resolvable today.
- **Machine-readable structure**: the agent can parse UniProt's structured JSON fields (domains, diseases, organism) rather than extracting them from prose.
- **Open access**: no authentication is required for basic PubMed and UniProt access — the agent works without credentials.

If the knowledge sources were a private, unstructured document store, citations would be unreliable — there would be no stable identifier to cite, and retrieval quality would depend on whoever structured (or failed to structure) the documents. The FAIR properties of PubMed and UniProt are not incidental — they are what make an agent approach to scientific research assistance viable.

---

## Streaming: why SSE over polling or WebSockets

The original `/query` endpoint blocks for 40–90 seconds while the agent runs.
The Streamlit UI shows nothing during this time — the user has no feedback on
whether the query is working or stuck.

**Option considered: polling.** The client submits a job, gets a job ID, and
polls `/status/{id}` every few seconds. This adds a job queue, a status store,
and extra round-trips. It is correct but over-engineered for a single-user
research assistant.

**Option considered: WebSockets.** Full bidirectional — appropriate when the
client also sends events mid-stream. For an agent that just needs to push
progress updates to the UI, WebSockets add complexity with no benefit.

**Chosen: Server-Sent Events (SSE).** A single HTTP connection that the server
holds open and writes to incrementally. The client reads chunks as they arrive.
Plain HTTP — no upgrade handshake, no persistent connection management, no
extra library. The Streamlit page uses the standard `requests` library with
`stream=True`.

The event types match the agent's natural checkpoints: tool selected,
tool result received, final answer produced, citations extracted. Each event
is independently useful — the user can see which papers are being searched
before the answer is ready.

SSE has one limitation: it is unidirectional. If a follow-up query needed to
interrupt an in-progress agent run, SSE would not support it. For v1
(one question at a time), this is not a constraint.

---

## Limitations

| Limitation | Impact |
|-----------|--------|
| CPU inference (~10s/LLM call) | 40–60s per query — acceptable for research use, not real-time |
| 8B parameter model | Reasoning errors on complex multi-hop questions |
| PubMed abstracts only | Full text requires journal access not available via Entrez |
| RAG corpus quality | Poor retrieval if the corpus was not seeded with relevant documents |
| No session memory | Each query starts fresh — no follow-up questions in v1 |
| Non-deterministic | Same question may produce different tool call order |

---

## Prompt engineering for tool-calling

### The problem: LLM stops too early

Llama 3.1 8B with tool-calling tends to stop after a single tool call. The
original system prompt included "use the minimum number of tool calls needed"
— the LLM interprets this aggressively, stopping as soon as it has any result
to work with, even if that result is only paper titles rather than content.

Observed behaviour:
- `pubmed_search` returns 10 paper titles
- LLM decides it has "enough" and generates an answer from titles only
- No `pubmed_fetch` is called — abstracts are never read
- Citations in the answer are real PMIDs but the LLM is summarising from titles,
  not from content — factual claims can be wrong

### The fix: explicit tool-use instructions

The system prompt must be explicit about the difference between `pubmed_search`
(returns titles only) and `pubmed_fetch` (returns full abstract). The LLM needs
to understand that a title is not a source — it is a pointer to a source.

Updated rule in the system prompt:
> `pubmed_search` returns titles and PMIDs only — not content. Always call
> `pubmed_fetch` on at least the top 2-3 results before citing a paper.
> A citation without a fetched abstract is not grounded.

### Why prompt quality is a design decision, not a tuning knob

The system prompt is the primary control surface for agent behaviour. A vague
instruction ("use minimum tool calls") produces vague behaviour. A specific
instruction ("fetch before citing") produces specific behaviour.

The tradeoff: more tool calls mean higher latency. For a research assistant,
an answer grounded in actual content is worth the extra 10-20 seconds. The
prompt should reflect this — accuracy over speed for this use case.

### Testing prompt changes

Prompt changes must be tested against the fixed benchmark questions in
`tests/test_agent.py` (e2e tests). A change that improves tool coverage on
one question may cause the agent to loop excessively on another. The benchmark
is the regression test for prompt quality.
