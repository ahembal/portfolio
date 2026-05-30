"""
LLM-as-judge scorer — evaluates RAG output quality without labelled data.

Scores three metrics per query:
  context_relevance  — are the retrieved chunks relevant to the question?
  faithfulness       — does the answer contain only claims from the chunks?
  answer_relevance   — does the answer address what was asked?

Each score is 0.0–1.0. The judge LLM is called once per metric per query.
Scores are probabilities estimated by the judge, not ground truth.

LLM interface
-------------
All functions accept `llm` as a plain callable: (prompt: str) -> str.
This keeps the judge independent of any specific LLM library. To use a
LangChain LLM, wrap it with the provided adapter:

    from src.evaluation.judge import langchain_adapter
    from langchain_ollama import ChatOllama

    llm = langchain_adapter(ChatOllama(model="llama3.1:8b", base_url="..."))
    evaluate(query, chunks, answer, llm)

Any other callable works too — an OpenAI client, Anthropic SDK, or a mock:

    llm = lambda prompt: "0.8"  # mock for tests
"""

import json
import re


def langchain_adapter(langchain_llm):
    """Wrap a LangChain LLM as a plain callable(prompt: str) -> str."""
    from langchain_core.messages import HumanMessage
    def call(prompt: str) -> str:
        return langchain_llm.invoke([HumanMessage(content=prompt)]).content
    return call


def _parse_score(text: str) -> float:
    """Extract a 0.0–1.0 score from judge output. Returns -1.0 if unparseable.

    Prefers decimal fractions (0.xxx, 1.0) over bare integers to avoid
    extracting a partial match from a longer number (e.g. "1" in "10.5").
    """
    match = re.search(r"\b(0\.\d+|1\.0+)\b", text)
    if not match:
        match = re.search(r"\b([01])\b", text)
    if match:
        return min(1.0, max(0.0, float(match.group(1))))
    return -1.0


def _call(llm, prompt: str) -> str:
    return llm(prompt)


def score_context_relevance(query: str, chunks: list[str], llm) -> float:
    """
    Score how relevant the retrieved chunks are to the query.

    Prompt strategy: ask the judge to count how many chunks are relevant,
    then normalise by total chunks. This is more reliable than asking for
    a single float directly.
    """
    chunks_text = "\n---\n".join(f"[{i+1}] {c}" for i, c in enumerate(chunks))
    prompt = f"""\
You are evaluating a retrieval system. Given a question and retrieved passages,
score how relevant the passages are to the question.

Question: {query}

Retrieved passages:
{chunks_text}

How many of the {len(chunks)} passages are relevant to the question?
Reply with only a JSON object: {{"relevant": <integer>, "total": {len(chunks)}}}
"""
    try:
        raw = _call(llm, prompt)
        data = json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group())
        return round(data["relevant"] / data["total"], 3)
    except Exception:
        return _parse_score(_call(llm, f"Score 0.0-1.0 how relevant these passages are to: {query}\nPassages: {chunks_text}\nScore:"))


def score_faithfulness(query: str, answer: str, chunks: list[str], llm) -> float:
    """
    Score whether the answer contains only claims supported by the chunks.

    Prompt strategy: ask the judge to list claims in the answer and check
    each against the chunks. Returns proportion of supported claims.
    """
    chunks_text = "\n---\n".join(f"[{i+1}] {c}" for i, c in enumerate(chunks))
    prompt = f"""\
You are evaluating whether an answer is faithful to its source passages.

Question: {query}

Source passages:
{chunks_text}

Answer: {answer}

List each factual claim in the answer. For each claim, state whether it is
supported by the source passages or not.
Reply with only a JSON object:
{{"supported": <integer>, "total": <integer>}}
"""
    try:
        raw = _call(llm, prompt)
        data = json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group())
        if data["total"] == 0:
            return 1.0
        return round(data["supported"] / data["total"], 3)
    except Exception:
        return _parse_score(_call(llm, f"Score 0.0-1.0 how faithful this answer is to the passages.\nAnswer: {answer}\nPassages: {chunks_text}\nScore:"))


def score_answer_relevance(query: str, answer: str, llm) -> float:
    """
    Score whether the answer addresses the question that was asked.
    """
    prompt = f"""\
You are evaluating whether an answer addresses the question asked.

Question: {query}
Answer: {answer}

Does the answer directly address the question? Score from 0.0 (completely
off-topic) to 1.0 (directly and completely answers the question).
Reply with only a JSON object: {{"score": <float between 0 and 1>}}
"""
    try:
        raw = _call(llm, prompt)
        data = json.loads(re.search(r"\{.*\}", raw, re.DOTALL).group())
        return round(min(1.0, max(0.0, float(data["score"]))), 3)
    except Exception:
        return _parse_score(_call(llm, f"Score 0.0-1.0 how well this answer addresses: {query}\nAnswer: {answer}\nScore:"))


def evaluate(
    query: str,
    chunks: list[str],
    answer: str,
    llm,
) -> dict:
    """
    Run all three metrics for a single query-retrieval-answer triple.

    Args:
        query:  the original question
        chunks: retrieved passages passed to the LLM
        answer: the generated answer
        llm:    callable(prompt: str) -> str — use langchain_adapter() for LangChain LLMs

    Returns:
        dict with keys: context_relevance, faithfulness, answer_relevance (all float 0–1)
    """
    return {
        "context_relevance": score_context_relevance(query, chunks, llm),
        "faithfulness":      score_faithfulness(query, answer, chunks, llm),
        "answer_relevance":  score_answer_relevance(query, answer, llm),
    }
