import asyncio
import json
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from prometheus_client import Counter, Histogram, generate_latest
from starlette.responses import PlainTextResponse

from src.api.schemas import Citation, HealthResponse, QueryRequest, QueryResponse, StepRecord
from src.agent.graph import build_graph
from src.tools.vector_store import search as rag_search

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

QUERY_TOTAL = Counter("query_total", "Total queries received")
QUERY_ERRORS = Counter("query_errors_total", "Queries that returned an error")
QUERY_LATENCY = Histogram(
    "query_latency_seconds",
    "Agent query latency",
    buckets=[1, 5, 10, 30, 60, 120],
)

# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

_state: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    _state["graph"] = build_graph()
    _state["ollama_url"] = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    _state["model"] = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    yield
    _state.clear()


app = FastAPI(title="Research Agent API", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    QUERY_TOTAL.inc()
    start = time.monotonic()

    from langchain_core.messages import HumanMessage

    try:
        graph = _state["graph"]
        invoke_input = {"messages": [HumanMessage(content=req.question)]}
        invoke_config = {"recursion_limit": req.max_steps * 2}
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None, lambda: graph.invoke(invoke_input, config=invoke_config)
        )
    except Exception as exc:
        QUERY_ERRORS.inc()
        raise HTTPException(status_code=500, detail=str(exc))

    latency_ms = (time.monotonic() - start) * 1000
    QUERY_LATENCY.observe(latency_ms / 1000)

    messages = result["messages"]
    answer = messages[-1].content if hasattr(messages[-1], "content") else str(messages[-1])

    # Extract citations and steps from tool messages
    citations: list[Citation] = []
    steps: list[StepRecord] = []
    step_num = 0

    from langchain_core.messages import ToolMessage, AIMessage
    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for call in msg.tool_calls:
                step_num += 1
                raw_output = ""
                # find matching tool message
                for m in messages:
                    if isinstance(m, ToolMessage) and m.tool_call_id == call["id"]:
                        raw_output = m.content
                        break
                steps.append(StepRecord(
                    step=step_num,
                    tool=call["name"],
                    input=call["args"],
                    output=raw_output[:500],
                ))
                # extract citations from tool output
                try:
                    data = json.loads(raw_output)
                    if call["name"] == "pubmed_search" and isinstance(data, list):
                        for item in data:
                            if "pmid" in item:
                                citations.append(Citation(
                                    type="pubmed",
                                    id=item["pmid"],
                                    title=item.get("title", ""),
                                    url=f"https://pubmed.ncbi.nlm.nih.gov/{item['pmid']}/",
                                ))
                    elif call["name"] == "pubmed_fetch" and isinstance(data, dict) and "pmid" in data:
                        citations.append(Citation(
                            type="pubmed",
                            id=data["pmid"],
                            title=data.get("title", ""),
                            url=data.get("url", ""),
                        ))
                    elif call["name"] == "uniprot_lookup" and isinstance(data, dict) and "accession" in data:
                        citations.append(Citation(
                            type="uniprot",
                            id=data["accession"],
                            title=data.get("protein_name", data.get("gene", "")),
                            url=data.get("url", ""),
                        ))
                except (json.JSONDecodeError, TypeError):
                    pass

    # Deduplicate citations by id
    seen: set[str] = set()
    unique_citations = []
    for c in citations:
        if c.id not in seen:
            seen.add(c.id)
            unique_citations.append(c)

    return QueryResponse(
        answer=answer,
        citations=unique_citations,
        steps=steps,
        latency_ms=round(latency_ms, 1),
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    import httpx
    ollama_status = "ok"
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{_state.get('ollama_url', 'http://ollama:11434')}/api/tags")
            if r.status_code != 200:
                ollama_status = "degraded"
    except Exception:
        ollama_status = "unreachable"

    vs_status = "ok"
    try:
        rag_search("test", k=1)
    except Exception:
        vs_status = "degraded"

    overall = "ok" if ollama_status == "ok" and vs_status == "ok" else "degraded"
    return HealthResponse(
        status=overall,
        ollama=ollama_status,
        vector_store=vs_status,
        model=_state.get("model", "llama3.1:8b"),
    )


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    return generate_latest()
