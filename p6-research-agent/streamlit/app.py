import os
import requests
import streamlit as st

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(page_title="Research Agent", layout="wide")
st.title("Life Science Research Agent")
st.caption("Powered by Llama 3.1 8B · PubMed · UniProt · Local RAG corpus")

question = st.text_input("Research question", placeholder="What is known about TP53 mutations in glioblastoma?")

if st.button("Ask", disabled=not question.strip()):
    with st.spinner("Agent is reasoning…"):
        try:
            resp = requests.post(
                f"{API_URL}/query",
                json={"question": question, "max_steps": 10},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.Timeout:
            st.error("Request timed out — the agent is still running. Try again or reduce query scope.")
            st.stop()
        except Exception as exc:
            st.error(f"Error: {exc}")
            st.stop()

    st.markdown("### Answer")
    st.markdown(data["answer"])

    if data.get("citations"):
        st.markdown("### Sources")
        for c in data["citations"]:
            label = f"[{c['type'].upper()}:{c['id']}] {c['title']}" if c["title"] else f"[{c['type'].upper()}:{c['id']}]"
            st.markdown(f"- [{label}]({c['url']})" if c["url"] else f"- {label}")

    with st.expander(f"Agent trace — {len(data['steps'])} tool calls · {data['latency_ms']:.0f} ms"):
        for step in data["steps"]:
            st.markdown(f"**Step {step['step']}: `{step['tool']}`**")
            st.json(step["input"])
            st.code(step["output"], language="json")
