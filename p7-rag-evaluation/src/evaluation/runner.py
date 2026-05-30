"""
Evaluation runner — runs the benchmark against the retrieval pipeline and
scores each query with the LLM judge.

Output is a list of per-query result dicts plus aggregate metrics.
Results can be compared across system versions to track improvement.

Answer generation
-----------------
The runner accepts an optional `answer_fn(query, chunks) -> str` parameter.
When provided, answers come from the real system under test (e.g. the p6
research agent API). When omitted, a simple inline prompt is used as a
stand-in — this is faster and requires no external service, but does not
reflect the actual agent's tool-calling pipeline or system prompt.

For meaningful evaluation of the full p6 system, pass:

    def answer_fn(query, chunks):
        import requests
        resp = requests.post("http://research-agent-api:8000/query",
                             json={"question": query}, timeout=120)
        return resp.json()["answer"]

    run(judge_llm, answer_fn=answer_fn)

The judge LLM is kept separate from the generator to avoid a model
evaluating its own outputs (self-referential scoring).
"""

import time
from src.evaluation.judge import evaluate
from src.evaluation.benchmark import BENCHMARK
from src.retrieval.pipeline import retrieve


def _default_answer_fn(query: str, chunks: list[str], llm) -> str:
    """Inline generation fallback — simplified proxy for the real agent."""
    context = "\n\n".join(chunks) if chunks else "No relevant passages retrieved."
    prompt = (
        f"Answer the following question using only the provided context.\n\n"
        f"Question: {query}\n\nContext:\n{context}\n\nAnswer:"
    )
    return llm(prompt)


def run(
    judge_llm,
    answer_fn=None,
    questions: list[dict] | None = None,
    top_n: int = 5,
) -> dict:
    """
    Run the evaluation benchmark.

    Args:
        judge_llm:  callable(prompt: str) -> str used only for scoring.
                    Use langchain_adapter() from src.evaluation.judge to wrap
                    a LangChain LLM.
        answer_fn:  callable(query, chunks) -> str that generates answers.
                    If None, falls back to inline generation with judge_llm
                    (not representative of the real system — see module docstring).
        questions:  list of benchmark entries (defaults to full BENCHMARK)
        top_n:      number of retrieved chunks to pass to answer_fn and judge

    Returns:
        dict with keys:
          results   — per-query list of dicts (question, path, scores, latency_ms)
          aggregate — mean scores across all queries
    """
    if questions is None:
        questions = BENCHMARK

    results = []

    for entry in questions:
        query = entry["question"]
        t0    = time.monotonic()

        retrieval = retrieve(query, top_n=top_n)
        chunks    = [r["text"] for r in retrieval["results"]]

        if answer_fn is not None:
            answer = answer_fn(query, chunks)
        else:
            answer = _default_answer_fn(query, chunks, judge_llm)

        scores     = evaluate(query, chunks, answer, judge_llm)
        latency_ms = round((time.monotonic() - t0) * 1000, 1)

        results.append({
            "question":          query,
            "complexity":        entry.get("complexity", "unknown"),
            "path":              retrieval["path"],
            "chunks_retrieved":  len(chunks),
            "answer":            answer,
            "scores":            scores,
            "latency_ms":        latency_ms,
        })

    # Aggregate — skip scores of -1.0 (unparseable judge output)
    def _mean(key: str) -> float:
        vals = [r["scores"][key] for r in results if r["scores"][key] >= 0]
        return round(sum(vals) / len(vals), 3) if vals else -1.0

    aggregate = {
        "context_relevance": _mean("context_relevance"),
        "faithfulness":      _mean("faithfulness"),
        "answer_relevance":  _mean("answer_relevance"),
        "n_queries":         len(results),
        "fast_path_pct":     round(sum(1 for r in results if r["path"] == "fast") / len(results) * 100, 1),
    }

    return {"results": results, "aggregate": aggregate}
