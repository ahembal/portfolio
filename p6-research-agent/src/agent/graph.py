"""
LangGraph agent: Reason → Act loop (standard ReAct pattern).

The LLM reasons and either calls tools or produces a final answer.
When it stops calling tools its last message IS the answer — no
separate synthesis step needed. A second LLM call without tools
reliably returns empty content with Llama 3.1 8B.
"""

import json
import os
from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.agent.prompts import SYSTEM_PROMPT
from src.tools import (
    pubmed_fetch,
    pubmed_search,
    rag_search,
    uniprot_lookup,
)


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

_TOOLS = [pubmed_search, pubmed_fetch, uniprot_lookup, rag_search]
_TOOL_MAP = {t.name: t for t in _TOOLS}


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def _build_llm() -> ChatOllama:
    return ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    ).bind_tools(_TOOLS)


def reason(state: AgentState) -> dict:
    """Call the LLM. Returns an AIMessage that may contain tool_calls."""
    llm = _build_llm()
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


def act(state: AgentState) -> dict:
    """Execute all tool calls in the last AIMessage and return ToolMessages."""
    last = state["messages"][-1]
    tool_messages: list[ToolMessage] = []

    for call in last.tool_calls:
        tool = _TOOL_MAP.get(call["name"])
        if tool is None:
            result = {"error": f"unknown tool: {call['name']}"}
        else:
            try:
                result = tool.invoke(call["args"])
            except Exception as exc:
                result = {"error": str(exc)}

        tool_messages.append(
            ToolMessage(
                content=json.dumps(result),
                tool_call_id=call["id"],
                name=call["name"],
            )
        )

    return {"messages": tool_messages}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def _router(state: AgentState) -> str:
    """After Reason: tool calls pending → Act, otherwise → END."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "act"
    return END


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("reason", reason)
    g.add_node("act", act)

    g.set_entry_point("reason")

    g.add_conditional_edges("reason", _router, {"act": "act", END: END})
    g.add_edge("act", "reason")

    return g.compile()


# ---------------------------------------------------------------------------
# Public helper
# ---------------------------------------------------------------------------

def run(question: str) -> str:
    """Run the agent on a single question and return the final answer text."""
    graph = build_graph()
    result = graph.invoke({"messages": [HumanMessage(content=question)]})
    last = result["messages"][-1]
    return last.content if hasattr(last, "content") else str(last)
