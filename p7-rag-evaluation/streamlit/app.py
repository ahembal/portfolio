"""
p7 RAG Evaluation Dashboard

Shows benchmark results: per-query scores, aggregate metrics,
retrieval path distribution, and per-metric breakdown.

Expects results in the format produced by src/evaluation/runner.run().
Can load from a JSON file or run a live evaluation against Ollama.
"""

import json
import os
import streamlit as st
import pandas as pd

st.set_page_config(page_title="RAG Evaluation", layout="wide")

st.title("RAG Evaluation Dashboard")
st.caption("p7 — Hybrid Retrieval + LLM-as-judge scoring")

# ---------------------------------------------------------------------------
# Load results
# ---------------------------------------------------------------------------

RESULTS_PATH = os.getenv("RESULTS_PATH", "/tmp/p7-eval-results.json")

st.sidebar.header("Results")
uploaded = st.sidebar.file_uploader("Load results JSON", type="json")

results_data = None

if uploaded:
    results_data = json.load(uploaded)
elif os.path.exists(RESULTS_PATH):
    with open(RESULTS_PATH) as f:
        results_data = json.load(f)

if results_data is None:
    st.info("No results loaded. Upload a results JSON file or run an evaluation first.")
    st.markdown("""
    **To generate results:**
    ```python
    from src.evaluation.runner import run
    from langchain_ollama import ChatOllama

    llm = ChatOllama(model="llama3.1:8b", base_url="http://ollama:11434")
    results = run(llm)

    import json
    with open("/tmp/p7-eval-results.json", "w") as f:
        json.dump(results, f)
    ```
    """)
    st.stop()

aggregate = results_data["aggregate"]
results   = results_data["results"]
df = pd.DataFrame([
    {
        "question":          r["question"],
        "complexity":        r["complexity"],
        "path":              r["path"],
        "context_relevance": r["scores"]["context_relevance"],
        "faithfulness":      r["scores"]["faithfulness"],
        "answer_relevance":  r["scores"]["answer_relevance"],
        "latency_ms":        r["latency_ms"],
        "chunks":            r["chunks_retrieved"],
    }
    for r in results
])

# ---------------------------------------------------------------------------
# Aggregate metrics
# ---------------------------------------------------------------------------

st.header("Aggregate scores")

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("Context relevance", f"{aggregate['context_relevance']:.2f}")
col2.metric("Faithfulness",      f"{aggregate['faithfulness']:.2f}")
col3.metric("Answer relevance",  f"{aggregate['answer_relevance']:.2f}")
col4.metric("Fast path",         f"{aggregate['fast_path_pct']:.0f}%")
col5.metric("Queries",           aggregate["n_queries"])

st.divider()

# ---------------------------------------------------------------------------
# Retrieval path distribution
# ---------------------------------------------------------------------------

st.header("Retrieval path distribution")

path_counts = df["path"].value_counts().reset_index()
path_counts.columns = ["path", "count"]
st.bar_chart(path_counts.set_index("path"))

# ---------------------------------------------------------------------------
# Per-query scores
# ---------------------------------------------------------------------------

st.header("Per-query scores")

# Colour code by complexity
complexity_filter = st.multiselect(
    "Filter by complexity",
    options=["simple", "complex"],
    default=["simple", "complex"],
)
filtered = df[df["complexity"].isin(complexity_filter)]

st.dataframe(
    filtered[[
        "question", "complexity", "path",
        "context_relevance", "faithfulness", "answer_relevance",
        "latency_ms", "chunks",
    ]].style
    .background_gradient(subset=["context_relevance", "faithfulness", "answer_relevance"],
                         cmap="RdYlGn", vmin=0, vmax=1)
    .format({
        "context_relevance": "{:.2f}",
        "faithfulness":      "{:.2f}",
        "answer_relevance":  "{:.2f}",
        "latency_ms":        "{:.0f}ms",
    }),
    use_container_width=True,
    hide_index=True,
)

# ---------------------------------------------------------------------------
# Per-metric breakdown
# ---------------------------------------------------------------------------

st.header("Score distribution by metric")

score_df = filtered[["context_relevance", "faithfulness", "answer_relevance"]].melt(
    var_name="metric", value_name="score"
)
score_df = score_df[score_df["score"] >= 0]  # exclude unparseable (-1.0)

metric_summary = score_df.groupby("metric")["score"].agg(["mean", "min", "max"]).reset_index()
metric_summary.columns = ["metric", "mean", "min", "max"]
st.dataframe(metric_summary.style.format({"mean": "{:.3f}", "min": "{:.3f}", "max": "{:.3f}"}),
             hide_index=True)

# ---------------------------------------------------------------------------
# Answers inspector
# ---------------------------------------------------------------------------

st.header("Answers inspector")
st.caption("Expand a query to see the generated answer.")

for _, row in filtered.iterrows():
    with st.expander(f"{row['complexity'].upper()} | {row['question'][:80]}"):
        col_a, col_b, col_c = st.columns(3)
        col_a.metric("Context relevance", f"{row['context_relevance']:.2f}")
        col_b.metric("Faithfulness",      f"{row['faithfulness']:.2f}")
        col_c.metric("Answer relevance",  f"{row['answer_relevance']:.2f}")
        answer = next(r["answer"] for r in results if r["question"] == row["question"])
        st.markdown(f"**Answer:**\n\n{answer}")
