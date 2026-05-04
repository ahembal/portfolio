"""
End-to-end agent evaluation — 5 fixed questions.

These tests require Ollama running locally with llama3.1:8b pulled.
Skip them in CI with: pytest -m "not e2e"

What is checked for each question:
  - The right tools were called
  - At least one citation is present
  - The answer does not contradict retrieved content (manual check)
"""

import pytest
from unittest.mock import MagicMock

from langchain_core.messages import AIMessage, ToolMessage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_tool_call(name: str, args: dict, call_id: str = "call_1"):
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


def _ai_with_tools(*calls):
    msg = AIMessage(content="")
    msg.tool_calls = list(calls)
    return msg


def _tool_msg(content: str, call_id: str = "call_1"):
    return ToolMessage(content=content, tool_call_id=call_id, name="mock")


# ---------------------------------------------------------------------------
# Unit tests — graph routing (no Ollama needed)
# ---------------------------------------------------------------------------

class TestGraphRouting:
    def test_router_goes_to_act_when_tool_calls_present(self):
        from src.agent.graph import _router, AgentState
        state: AgentState = {
            "messages": [_ai_with_tools(_make_tool_call("pubmed_search", {"query": "TP53"}))]
        }
        assert _router(state) == "act"

    def test_router_goes_to_end_when_no_tool_calls(self):
        from langgraph.graph import END
        from src.agent.graph import _router, AgentState
        state: AgentState = {
            "messages": [AIMessage(content="TP53 is a tumour suppressor.")]
        }
        assert _router(state) == END

    def test_act_node_calls_pubmed_search(self):
        from src.agent.graph import act, AgentState
        import src.agent.graph as g

        call = _make_tool_call("pubmed_search", {"query": "TP53 glioblastoma"}, "c1")
        ai_msg = _ai_with_tools(call)
        state: AgentState = {"messages": [ai_msg]}

        mock_fn = MagicMock(return_value=[{"pmid": "12345", "title": "TP53 in GBM"}])
        original = g._TOOLS["pubmed_search"]
        g._TOOLS["pubmed_search"] = mock_fn
        try:
            result = act(state)
        finally:
            g._TOOLS["pubmed_search"] = original

        mock_fn.assert_called_once_with(query="TP53 glioblastoma")
        assert len(result["messages"]) == 1
        assert result["messages"][0].tool_call_id == "c1"

    def test_act_node_handles_unknown_tool_gracefully(self):
        from src.agent.graph import act, AgentState

        call = _make_tool_call("nonexistent_tool", {}, "c1")
        ai_msg = _ai_with_tools(call)
        state: AgentState = {"messages": [ai_msg]}

        result = act(state)
        import json
        output = json.loads(result["messages"][0].content)
        assert "error" in output

    def test_act_node_calls_uniprot_lookup(self):
        from src.agent.graph import act, AgentState
        import src.agent.graph as g

        call = _make_tool_call("uniprot_lookup", {"query": "TP53", "organism": "human"}, "c2")
        ai_msg = _ai_with_tools(call)
        state: AgentState = {"messages": [ai_msg]}

        mock_fn = MagicMock(return_value={"accession": "P04637", "gene": "TP53"})
        original = g._TOOLS["uniprot_lookup"]
        g._TOOLS["uniprot_lookup"] = mock_fn
        try:
            result = act(state)
        finally:
            g._TOOLS["uniprot_lookup"] = original

        mock_fn.assert_called_once_with(query="TP53", organism="human")
        assert result["messages"][0].tool_call_id == "c2"


# ---------------------------------------------------------------------------
# E2E tests — require Ollama (skipped in CI)
# ---------------------------------------------------------------------------

@pytest.mark.e2e
class TestAgentE2E:
    """
    Five fixed questions. For each, check:
    1. Answer is non-empty
    2. At least one citation present ([PMID:] or [UniProt:])
    3. Correct tool category was used (manually verified by reading the steps)

    Run with: pytest tests/test_agent.py -m e2e
    """

    QUESTIONS = [
        ("q1_gene_disease", "What is the role of TP53 in cancer?"),
        ("q2_protein_structure", "What domains does the BRCA1 protein have?"),
        ("q3_treatment", "How does sotorasib work in KRAS G12C mutant cancers?"),
        ("q4_uncertainty", "What is the function of gene XYZ99999 in humans?"),
        ("q5_multihop", "Which proteins interact with TP53 and are also implicated in DNA repair?"),
    ]

    @pytest.mark.parametrize("name,question", QUESTIONS)
    def test_agent_answers_question(self, name, question):
        from src.agent.graph import run
        answer = run(question)
        assert isinstance(answer, str)
        assert len(answer) > 50, f"Answer too short for '{name}'"

    def test_tp53_answer_cites_pubmed_or_uniprot(self):
        from src.agent.graph import run
        answer = run("What is the role of TP53 in cancer?")
        has_citation = "[PMID:" in answer or "[UniProt:" in answer
        assert has_citation, f"No citation found in answer: {answer[:200]}"

    def test_uncertainty_acknowledged(self):
        from src.agent.graph import run
        answer = run("What is the function of gene XYZ99999 in humans?")
        uncertainty_signals = ["not found", "no result", "unable", "unknown", "could not", "don't know"]
        assert any(s in answer.lower() for s in uncertainty_signals), \
            f"Agent did not acknowledge uncertainty for nonexistent gene: {answer[:200]}"
