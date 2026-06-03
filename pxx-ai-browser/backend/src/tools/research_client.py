"""
Thin proxy to p6 research agent's SSE stream endpoint.
The browser's Research companion delegates here — all tool logic
(PubMed, UniProt, ChromaDB RAG) lives in p6 and is not duplicated.

p6 SSE event types (passed through unchanged):
  { type: "tool_call",   tool, args }
  { type: "tool_result", tool, content }
  { type: "answer",      content }
  { type: "citations",   citations }
  { type: "done" }
  { type: "error",       message }
"""

import json
import os
from typing import AsyncGenerator

import httpx

P6_URL = os.getenv("P6_RESEARCH_AGENT_URL", "http://research-agent-api:8000")


async def stream_research(question: str) -> AsyncGenerator[str, None]:
    url = f"{P6_URL}/query/stream"
    params = {"question": question, "max_steps": "10"}

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream("GET", url, params=params) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        # relay the SSE event as-is — p6 and this backend share the same schema
                        yield f"{line}\n\n"
    except httpx.HTTPStatusError as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': f'p6 returned {exc.response.status_code}'})}\n\n"
    except Exception as exc:
        yield f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"

    yield f"data: {json.dumps({'type': 'done'})}\n\n"
