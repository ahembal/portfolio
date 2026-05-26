import json
import os

import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://research-agent-api:8000")

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
    args  = step.get("args") or step.get("input", {})
    if step["tool"] == "pubmed_search":
        return f'{icon} {label} for **"{args.get("query", "")}"**'
    if step["tool"] == "pubmed_fetch":
        return f'{icon} {label} PMID:{args.get("pmid", "")}'
    if step["tool"] == "uniprot_lookup":
        return f'{icon} {label} **{args.get("query", "")}** ({args.get("organism", "human")})'
    if step["tool"] == "rag_search":
        return f'{icon} {label} for **"{args.get("query", "")}"**'
    return f'{icon} {label}'


def _step_result(content: str) -> str:
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return content[:200]
    if isinstance(data, list):
        if data and "error" in data[0]:
            return f"⚠️ {data[0]['error']}"
        return f"Found {len(data)} result(s)"
    if isinstance(data, dict):
        if "error" in data:
            return f"⚠️ {data['error']}"
        if "title" in data:
            return f'**{data["title"][:80]}**'
        if "gene" in data:
            return f'**{data["gene"]}** ({data.get("accession", "")})'
    return str(content)[:200]


# ---------------------------------------------------------------------------
# Session state initialisation — persists across page navigation
# ---------------------------------------------------------------------------

for key, default in {
    "ra_question":  "",
    "ra_answer":    "",
    "ra_citations": [],
    "ra_steps":     [],
    "ra_latency":   0.0,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# Page layout
# ---------------------------------------------------------------------------

st.set_page_config(page_title="Research Agent", layout="wide")
st.title("🧬 Life Science Research Agent")
st.caption("Llama 3.1 8B · LangGraph · PubMed · UniProt · Local RAG corpus")

with st.sidebar:
    st.header("Available tools")
    st.markdown("""
**🔍 PubMed search**
Searches NCBI PubMed for biomedical literature.

**📄 PubMed fetch**
Retrieves full abstract and metadata by PMID.

**🧬 UniProt lookup**
Looks up a protein — domains, diseases, function.

**📚 RAG corpus search**
Searches pre-indexed background documents.
""")
    st.divider()
    st.caption("Citations appear as `[PMID:xxxxx]` or `[UniProt:Pxxxxx]`.")
    st.caption("First query ~60–90 s on CPU.")
    if st.button("Clear session"):
        for key in ["ra_question", "ra_answer", "ra_citations", "ra_steps", "ra_latency"]:
            st.session_state[key] = "" if key in ("ra_question", "ra_answer") else [] if "citations" in key or "steps" in key else 0.0
        st.rerun()

question = st.text_input(
    "Research question",
    value=st.session_state.ra_question,
    placeholder="What is known about TP53 mutations in glioblastoma?",
)

if st.button("Ask", disabled=not question.strip()):
    st.session_state.ra_question  = question
    st.session_state.ra_answer    = ""
    st.session_state.ra_citations = []
    st.session_state.ra_steps     = []
    st.session_state.ra_latency   = 0.0

    # --- Streaming ---
    answer_placeholder   = st.empty()
    steps_placeholder    = st.empty()

    steps_live: list[dict] = []
    pending_call: dict | None = None

    try:
        with requests.get(
            f"{API_URL}/query/stream",
            params={"question": question, "max_steps": 10},
            stream=True,
            timeout=180,
        ) as resp:
            resp.raise_for_status()
            import time
            t0 = time.monotonic()

            for raw_line in resp.iter_lines():
                if not raw_line:
                    continue
                line = raw_line.decode("utf-8") if isinstance(raw_line, bytes) else raw_line
                if not line.startswith("data: "):
                    continue
                event = json.loads(line[6:])

                if event["type"] == "tool_call":
                    pending_call = {"tool": event["tool"], "args": event["args"], "content": ""}
                    steps_live.append(pending_call)
                    with steps_placeholder.container():
                        for i, s in enumerate(steps_live):
                            st.markdown(f"**Step {i+1}** — {_step_summary(s)}")
                            if s["content"]:
                                st.markdown(f"> {_step_result(s['content'])}")

                elif event["type"] == "tool_result":
                    # Attach result to the last matching call
                    for s in reversed(steps_live):
                        if s["tool"] == event["tool"] and not s["content"]:
                            s["content"] = event["content"]
                            break
                    with steps_placeholder.container():
                        for i, s in enumerate(steps_live):
                            st.markdown(f"**Step {i+1}** — {_step_summary(s)}")
                            if s["content"]:
                                st.markdown(f"> {_step_result(s['content'])}")

                elif event["type"] == "answer":
                    st.session_state.ra_answer  = event["content"]
                    st.session_state.ra_latency = round((time.monotonic() - t0) * 1000, 1)
                    answer_placeholder.markdown(event["content"])

                elif event["type"] == "citations":
                    st.session_state.ra_citations = event["citations"]

                elif event["type"] == "done":
                    st.session_state.ra_steps = [
                        {"step": i + 1, "tool": s["tool"], "input": s["args"], "output": s["content"]}
                        for i, s in enumerate(steps_live)
                    ]
                    break

                elif event["type"] == "error":
                    st.error(f"Agent error: {event['message']}")
                    st.stop()

    except requests.exceptions.ConnectionError:
        st.error("Cannot reach the API — is the research-agent-api container running?")
        st.stop()
    except requests.exceptions.Timeout:
        st.error("Request timed out after 180 s — try a simpler question.")
        st.stop()
    except Exception as exc:
        st.error(f"Error: {exc}")
        st.stop()

    st.rerun()


# ---------------------------------------------------------------------------
# Display stored result (persists across page navigation)
# ---------------------------------------------------------------------------

if st.session_state.ra_answer:
    st.markdown("### Answer")
    st.markdown(st.session_state.ra_answer)

    if st.session_state.ra_citations:
        st.markdown("### Sources")
        for c in st.session_state.ra_citations:
            label = f"[{c['type'].upper()}:{c['id']}] {c['title']}" if c.get("title") else f"[{c['type'].upper()}:{c['id']}]"
            st.markdown(f"- [{label}]({c['url']})" if c.get("url") else f"- {label}")

    steps = st.session_state.ra_steps
    latency = st.session_state.ra_latency
    with st.expander(
        f"🔎 How the agent answered — {len(steps)} tool call(s) · {latency/1000:.1f}s",
        expanded=False,
    ):
        for step in steps:
            st.markdown(f"**Step {step['step']}** — {_step_summary(step)}")
            st.markdown(f"> {_step_result(step['output'])}")
            with st.expander("Raw output", expanded=False):
                try:
                    st.json(json.loads(step["output"]))
                except (json.JSONDecodeError, TypeError):
                    st.code(step["output"])
            st.divider()
