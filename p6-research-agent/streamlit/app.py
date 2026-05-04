import json
import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

TOOL_ICONS = {
    "pubmed_search":  "🔍",
    "pubmed_fetch":   "📄",
    "uniprot_lookup": "🧬",
    "rag_search":     "📚",
}

TOOL_LABELS = {
    "pubmed_search":  "Searching PubMed",
    "pubmed_fetch":   "Fetching article",
    "uniprot_lookup": "Looking up protein",
    "rag_search":     "Searching local corpus",
}


def _step_summary(step: dict) -> str:
    icon  = TOOL_ICONS.get(step["tool"], "🔧")
    label = TOOL_LABELS.get(step["tool"], step["tool"])
    args  = step["input"]

    if step["tool"] == "pubmed_search":
        return f'{icon} {label} for **"{args.get("query", "")}"**'
    if step["tool"] == "pubmed_fetch":
        return f'{icon} {label} PMID:{args.get("pmid", "")}'
    if step["tool"] == "uniprot_lookup":
        return f'{icon} {label} **{args.get("query", "")}** ({args.get("organism", "human")})'
    if step["tool"] == "rag_search":
        return f'{icon} {label} for **"{args.get("query", "")}"**'
    return f'{icon} {label}'


def _step_result(step: dict) -> str:
    try:
        data = json.loads(step["output"])
    except (json.JSONDecodeError, TypeError):
        return step["output"]

    tool = step["tool"]
    if tool == "pubmed_search" and isinstance(data, list):
        if data and "error" in data[0]:
            return f"⚠️ {data[0]['error']}"
        return f"Found {len(data)} article(s): " + ", ".join(
            f'"{r.get("title","")[:60]}…" (PMID:{r.get("pmid","")})' for r in data[:3]
        )
    if tool == "pubmed_fetch" and isinstance(data, dict):
        if "error" in data:
            return f"⚠️ {data['error']}"
        return f'**{data.get("title","")}** · {data.get("journal","")} {data.get("year","")}'
    if tool == "uniprot_lookup" and isinstance(data, dict):
        if "error" in data:
            return f"⚠️ {data['error']}"
        diseases = ", ".join(data.get("diseases", [])[:3])
        return (
            f'**{data.get("gene","")}** ({data.get("accession","")}) · '
            f'{data.get("organism","")} · {data.get("length","")} aa'
            + (f' · diseases: {diseases}' if diseases else "")
        )
    if tool == "rag_search" and isinstance(data, list):
        if not data:
            return "No relevant passages found."
        return f"Retrieved {len(data)} passage(s) — top score {data[0].get('score', 0):.2f}"
    return step["output"][:200]


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Research Agent", layout="wide")
st.title("Life Science Research Agent")
st.caption("Powered by Llama 3.1 8B · PubMed · UniProt · Local RAG corpus")

with st.sidebar:
    st.header("Available tools")
    st.markdown("""
**🔍 PubMed search**
Searches NCBI PubMed for biomedical literature by keyword.

**📄 PubMed fetch**
Retrieves the full abstract and metadata for a specific article by PMID.

**🧬 UniProt lookup**
Looks up a protein or gene in UniProt — returns domains, diseases, and function.

**📚 RAG corpus search**
Searches a local vector store of pre-indexed background documents.
""")
    st.divider()
    st.caption("Citations appear inline as `[PMID:xxxxx]` or `[UniProt:Pxxxxx]`.")
    st.caption("First query may take 60–90 s (CPU inference).")

question = st.text_input(
    "Research question",
    placeholder="What is known about TP53 mutations in glioblastoma?",
)

if st.button("Ask", disabled=not question.strip()):
    with st.spinner("Agent is reasoning… (first query may take 60–90 s on CPU)"):
        try:
            resp = requests.post(
                f"{API_URL}/query",
                json={"question": question, "max_steps": 10},
                timeout=180,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout:
            st.error("Request timed out — try a simpler question or increase max_steps.")
            st.stop()
        except Exception as exc:
            st.error(f"Error: {exc}")
            st.stop()

    # --- Answer ---
    st.markdown("### Answer")
    if data["answer"]:
        st.markdown(data["answer"])
    else:
        st.warning("The agent completed but returned an empty answer. See the trace below.")

    # --- Sources ---
    if data.get("citations"):
        st.markdown("### Sources")
        for c in data["citations"]:
            label = f"[{c['type'].upper()}:{c['id']}] {c['title']}" if c["title"] else f"[{c['type'].upper()}:{c['id']}]"
            st.markdown(f"- [{label}]({c['url']})" if c["url"] else f"- {label}")

    # --- Agent trace ---
    steps = data.get("steps", [])
    latency = data.get("latency_ms", 0)

    with st.expander(
        f"🔎 How the agent answered — {len(steps)} tool call(s) · {latency/1000:.1f}s",
        expanded=True,
    ):
        if not steps:
            st.info("No tool calls recorded.")
        for step in steps:
            st.markdown(f"**Step {step['step']}** — {_step_summary(step)}")
            result_text = _step_result(step)
            st.markdown(f"> {result_text}")
            with st.expander("Raw output", expanded=False):
                try:
                    st.json(json.loads(step["output"]))
                except (json.JSONDecodeError, TypeError):
                    st.code(step["output"])
            st.divider()
