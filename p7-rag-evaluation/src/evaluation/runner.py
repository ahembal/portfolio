"""
Evaluation runner — runs the benchmark against the retrieval pipeline and
scores each query with the LLM judge.

Output is a list of per-query result dicts plus aggregate metrics.
Results can be compared across system versions to track improvement.
"""

import time
from src.evaluation.judge import evaluate
from src.evaluation.benchmark import BENCHMARK
from src.retrieval.pipeline import retrieve


def run(
    llm,
    questions: list[dict] | None = None,
    top_n: int = 5,
) -> dict:
    """
    Run the evaluation benchmark.

    Args:
        llm:       LangChain-compatible LLM for the judge
        questions: list of benchmark entries (defaults to full BENCHMARK)
        top_n:     number of retrieved chunks to pass to judge and LLM

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

        # Generate answer from chunks using the judge LLM
        from langchain_core.messages import HumanMessage
        context  = "\n\n".join(chunks) if chunks else "No relevant passages retrieved."
        answer_prompt = (
            f"Answer the following question using only the provided context.\n\n"
            f"Question: {query}\n\nContext:\n{context}\n\nAnswer:"
        )
        answer = llm.invoke([HumanMessage(content=answer_prompt)]).content

        scores     = evaluate(query, chunks, answer, llm)
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
