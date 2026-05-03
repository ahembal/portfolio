"""
LangGraph agent: Reason → Act → Respond loop.

State carries the full conversation history and all tool outputs so every
node has complete context. Control flow is explicit: the router decides after
each Act step whether to loop back (more tool calls pending) or move to Respond.
"""

import json
import os
from typing import Annotated, Any

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

_TOOLS: dict[str, Any] = {
    "pubmed_search": pubmed_search,
    "pubmed_fetch": pubmed_fetch,
    "uniprot_lookup": uniprot_lookup,
    "rag_search": rag_search,
}

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "pubmed_search",
            "description": "Search PubMed for articles matching a keyword query.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "max_results": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "pubmed_fetch",
            "description": "Fetch the full abstract and metadata for a single PubMed article.",
            "parameters": {
                "type": "object",
                "properties": {
                    "pmid": {"type": "string"},
                },
                "required": ["pmid"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "uniprot_lookup",
            "description": "Look up a protein or gene in UniProt.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "organism": {"type": "string", "default": "human"},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rag_search",
            "description": "Search the local vector store for relevant passages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "k": {"type": "integer", "default": 5},
                },
                "required": ["query"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def _build_llm() -> ChatOllama:
    return ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    ).bind_tools(_TOOL_SCHEMAS)


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
        fn = _TOOLS.get(call["name"])
        if fn is None:
            result = {"error": f"unknown tool: {call['name']}"}
        else:
            try:
                result = fn(**call["args"])
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


def respond(state: AgentState) -> dict:
    """Final answer — call the LLM one more time without tools to synthesise."""
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    )
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

def _router(state: AgentState) -> str:
    """After Reason: if the LLM emitted tool calls → Act, otherwise → Respond."""
    last = state["messages"][-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "act"
    return "respond"


# ---------------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    g = StateGraph(AgentState)

    g.add_node("reason", reason)
    g.add_node("act", act)
    g.add_node("respond", respond)

    g.set_entry_point("reason")

    g.add_conditional_edges("reason", _router, {"act": "act", "respond": "respond"})
    g.add_edge("act", "reason")   # loop: Act → Reason → Act → … until no tool calls
    g.add_edge("respond", END)

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
