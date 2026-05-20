"""
RAG vs SPARQL benchmark runner for p9.

Runs the 20 benchmark questions through both systems and produces a
structured results table for docs/comparison.md.

Structured questions (type="structured"):
  SPARQL  — executes the embedded query, records exact results.
  RAG     — calls p7's runner (retrieve + LLM generate + judge score).
  Winner  — SPARQL result is ground truth; RAG scored by p7's LLM judge.

Open-ended questions (type="open_ended"):
  RAG     — full retrieve + generate + judge via p7's runner.
  SPARQL  — not applicable; recorded as N/A.

Usage:
    # Full comparison (Fuseki + p7 + Ollama required):
    python scripts/run_comparison.py

    # SPARQL only (no p7 / LLM required):
    python scripts/run_comparison.py --sparql-only

    # Custom endpoint:
    P9_SPARQL_ENDPOINT=http://<node-ip>:30900/p9/sparql python scripts/run_comparison.py

Output:
    results/comparison_<timestamp>.json
    results/comparison_<timestamp>.md    ← paste into docs/comparison.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.benchmark import BENCHMARK
from src.sparql import SPARQLClient

# ── p7 integration ────────────────────────────────────────────────────────────

P7_ROOT = Path(__file__).parent.parent.parent / "p7-rag-evaluation"
sys.path.insert(0, str(P7_ROOT))

try:
    from langchain_ollama import ChatOllama
    from src.evaluation.judge import evaluate as judge_evaluate  # type: ignore
    from src.retrieval.pipeline import retrieve as p7_retrieve   # type: ignore
    from langchain_core.messages import HumanMessage             # type: ignore
    P7_AVAILABLE = True
except ImportError:
    P7_AVAILABLE = False


def _make_llm() -> object:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
    model    = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    return ChatOllama(model=model, base_url=base_url)


# ── SPARQL runner ─────────────────────────────────────────────────────────────

def _run_sparql(client: SPARQLClient, sparql: str) -> tuple[list[dict], float]:
    """Execute a SPARQL query and return (rows, latency_ms)."""
    t0 = time.monotonic()
    rows = client.query(sparql)
    return rows, round((time.monotonic() - t0) * 1000, 1)


def _rows_to_prose(rows: list[dict]) -> str:
    """Convert SPARQL result rows to a readable string."""
    if not rows:
        return "No results found."
    if len(rows) == 1 and list(rows[0].keys()) == ["count"]:
        return f"Count: {rows[0]['count']}"
    lines = [", ".join(f"{k}={v}" for k, v in row.items()) for row in rows[:20]]
    suffix = f"\n(and {len(rows) - 20} more)" if len(rows) > 20 else ""
    return "\n".join(lines) + suffix


# ── RAG runner ────────────────────────────────────────────────────────────────

def _run_rag(question: str, llm) -> tuple[str, dict, float]:
    """
    Retrieve context from p7, generate an answer, and score it.

    Returns (answer, scores, latency_ms).
    scores keys: context_relevance, faithfulness, answer_relevance.
    """
    t0 = time.monotonic()

    retrieval = p7_retrieve(question, top_n=5)
    chunks    = [r["text"] for r in retrieval["results"]]
    context   = "\n\n".join(chunks) if chunks else "No relevant passages retrieved."

    answer = llm.invoke([HumanMessage(content=(
        f"Answer the following question using only the provided context.\n\n"
        f"Question: {question}\n\nContext:\n{context}\n\nAnswer:"
    ))]).content

    scores     = judge_evaluate(question, chunks, answer, llm)
    latency_ms = round((time.monotonic() - t0) * 1000, 1)

    return answer, scores, latency_ms


# ── Main runner ───────────────────────────────────────────────────────────────

def run(sparql_only: bool = False) -> dict:
    client  = SPARQLClient()
    llm     = _make_llm() if (P7_AVAILABLE and not sparql_only) else None
    results = []

    for entry in BENCHMARK:
        q      = entry["question"]
        qtype  = entry["type"]
        sparql = entry.get("sparql")

        row: dict = {
            "question":      q,
            "type":          qtype,
            "sparql_rows":   None,
            "sparql_prose":  None,
            "sparql_ms":     None,
            "rag_answer":    None,
            "rag_scores":    None,
            "rag_ms":        None,
        }

        if sparql:
            try:
                rows, ms = _run_sparql(client, sparql)
                row["sparql_rows"]  = rows
                row["sparql_prose"] = _rows_to_prose(rows)
                row["sparql_ms"]    = ms
            except Exception as exc:
                row["sparql_prose"] = f"ERROR: {exc}"

        if llm and not sparql_only:
            try:
                answer, scores, ms = _run_rag(q, llm)
                row["rag_answer"] = answer
                row["rag_scores"] = scores
                row["rag_ms"]     = ms
            except Exception as exc:
                row["rag_answer"] = f"ERROR: {exc}"

        results.append(row)
        print(f"  [{qtype:10}] {q[:70]}")

    return {"results": results, "timestamp": datetime.utcnow().isoformat()}


# ── Markdown output ───────────────────────────────────────────────────────────

def _to_markdown(data: dict) -> str:
    lines = [
        "# RAG vs SPARQL — Benchmark Results",
        f"*Generated: {data['timestamp']}*",
        "",
        "## Structured questions",
        "",
        "| Question | SPARQL answer | RAG faithfulness | RAG relevance | SPARQL ms | RAG ms |",
        "|----------|--------------|-----------------|---------------|-----------|--------|",
    ]
    for r in data["results"]:
        if r["type"] != "structured":
            continue
        sc  = r["rag_scores"] or {}
        lines.append(
            f"| {r['question'][:55]} "
            f"| {(r['sparql_prose'] or '—')[:40]} "
            f"| {sc.get('faithfulness', '—')} "
            f"| {sc.get('answer_relevance', '—')} "
            f"| {r['sparql_ms'] or '—'} "
            f"| {r['rag_ms'] or '—'} |"
        )

    lines += [
        "",
        "## Open-ended questions",
        "",
        "| Question | RAG faithfulness | RAG relevance | RAG ms |",
        "|----------|-----------------|---------------|--------|",
    ]
    for r in data["results"]:
        if r["type"] != "open_ended":
            continue
        sc = r["rag_scores"] or {}
        lines.append(
            f"| {r['question'][:55]} "
            f"| {sc.get('faithfulness', '—')} "
            f"| {sc.get('answer_relevance', '—')} "
            f"| {r['rag_ms'] or '—'} |"
        )

    return "\n".join(lines)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sparql-only", action="store_true",
                        help="Run SPARQL queries only — no LLM or p7 required")
    args = parser.parse_args()

    if not P7_AVAILABLE and not args.sparql_only:
        print("p7 not available — falling back to --sparql-only. "
              "Run from portfolio root with p7 dependencies installed to enable RAG.")
        args.sparql_only = True

    print("Running benchmark...")
    data = run(sparql_only=args.sparql_only)

    out = Path("results")
    out.mkdir(exist_ok=True)
    ts = data["timestamp"].replace(":", "-").replace(".", "-")

    (out / f"comparison_{ts}.json").write_text(json.dumps(data, indent=2))
    md_path = out / f"comparison_{ts}.md"
    md_path.write_text(_to_markdown(data))

    print(f"\nResults: {out}/comparison_{ts}.*")
    print("Copy the .md table into docs/comparison.md.")


if __name__ == "__main__":
    main()
