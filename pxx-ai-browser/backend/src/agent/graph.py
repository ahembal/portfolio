"""
ReAct agent for AI Browser companions.
Same pattern as p6 — reason → act loop via LangGraph.

Two graphs:
  build_graph()       — reading companions (Docs, GitHub): fetch_page_text only
  build_action_graph()— acting companion: browser_* tools for clicking/typing/navigating

Research companion bypasses both and proxies directly to p6.
"""

import json
import logging
import os
from typing import Annotated

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from src.agent.prompts import ACTION_SYSTEM_PROMPT, DOCS_SYSTEM_PROMPT
from src.tools.browser_actions import (
    browser_click,
    browser_get_elements,
    browser_navigate,
    browser_screenshot,
    browser_type,
)
from src.tools.page_reader import fetch_page_text

log = logging.getLogger("ai-browser.agent")

_READ_TOOLS = [fetch_page_text]
_ACTION_TOOLS = [
    browser_screenshot,
    browser_get_elements,
    browser_click,
    browser_type,
    browser_navigate,
    fetch_page_text,  # agent can still read pages during action tasks
]


class AgentState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]


def _build_llm(tools: list, system_prompt: str):
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),
    ).bind_tools(tools)
    return llm, system_prompt


def _make_nodes(tools: list, system_prompt: str):
    tool_map = {t.name: t for t in tools}

    def reason(state: AgentState) -> dict:
        llm, prompt = _build_llm(tools, system_prompt)
        messages = [{"role": "system", "content": prompt}] + state["messages"]
        return {"messages": [llm.invoke(messages)]}

    def act(state: AgentState) -> dict:
        last = state["messages"][-1]
        tool_messages: list[ToolMessage] = []
        for call in last.tool_calls:
            tool = tool_map.get(call["name"])
            if tool is None:
                result = {"error": f"unknown tool: {call['name']}"}
            else:
                try:
                    log.info("tool_invoked", extra={"tool": call["name"]})
                    result = tool.invoke(call["args"])
                    if isinstance(result, dict) and "error" in result:
                        log.warning("tool_error", extra={"tool": call["name"], "error": result["error"]})
                except Exception as exc:
                    log.error("tool_exception", extra={"tool": call["name"], "error": str(exc)})
                    result = {"error": str(exc)}
            tool_messages.append(
                ToolMessage(
                    content=json.dumps(result),
                    tool_call_id=call["id"],
                    name=call["name"],
                )
            )
        return {"messages": tool_messages}

    return reason, act


def _assemble(reason, act) -> StateGraph:
    g = StateGraph(AgentState)
    g.add_node("reason", reason)
    g.add_node("act", act)
    g.set_entry_point("reason")
    g.add_conditional_edges(
        "reason",
        lambda s: "act" if (isinstance(s["messages"][-1], AIMessage) and s["messages"][-1].tool_calls) else END,
        {"act": "act", END: END},
    )
    g.add_edge("act", "reason")
    return g.compile()


def build_graph() -> StateGraph:
    """Reading companions — Docs Navigator, GitHub."""
    reason, act = _make_nodes(_READ_TOOLS, DOCS_SYSTEM_PROMPT)
    return _assemble(reason, act)


def build_action_graph() -> StateGraph:
    """Acting companion — can click, type, navigate the live browser."""
    reason, act = _make_nodes(_ACTION_TOOLS, ACTION_SYSTEM_PROMPT)
    return _assemble(reason, act)
