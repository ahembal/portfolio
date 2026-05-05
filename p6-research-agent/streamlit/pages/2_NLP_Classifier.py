import os
import requests
import streamlit as st

API_URL = os.getenv("NLP_API_URL", "http://nlp-inference-api.nlp-inference.svc.cluster.local:8000")

LABEL_COLOURS = {
    "BACKGROUND":  "#4A90D9",
    "OBJECTIVE":   "#E67E22",
    "METHODS":     "#27AE60",
    "RESULTS":     "#8E44AD",
    "CONCLUSIONS": "#C0392B",
}

SAMPLE_ABSTRACT = """Background: Colorectal cancer is one of the leading causes of cancer mortality worldwide.
Objective: We evaluated the efficacy of combination chemotherapy in patients with metastatic colorectal cancer.
Methods: Patients were randomly assigned to receive FOLFOX or FOLFIRI in a multicentre randomised controlled trial.
Results: Overall survival was 18.2 months in the FOLFOX arm versus 16.8 months in the FOLFIRI arm (p=0.42).
Conclusions: Both regimens showed comparable efficacy with different toxicity profiles."""

st.set_page_config(page_title="NLP Classifier", layout="wide")
st.title("🧪 PubMed Abstract Sentence Classifier")
st.caption("DistilBERT · Fine-tuned on PubMed RCT 20k · Accuracy 86.8% · Macro F1 0.81")

with st.sidebar:
    st.header("About")
    st.markdown("""
**Model:** DistilBERT fine-tuned on PubMed RCT 20k — 177k sentences from clinical trial abstracts.

**Task:** Classify each sentence into its structural role:

""")
    for label, colour in LABEL_COLOURS.items():
        st.markdown(
            f'<span style="background-color:{colour};color:white;padding:2px 8px;'
            f'border-radius:4px;font-size:0.8em">{label}</span>',
            unsafe_allow_html=True,
        )
    st.markdown("""
**Why DistilBERT over BERT:**
40% smaller, 60% faster, 97% of BERT's NLP benchmark performance — right for CPU serving.

**Infrastructure:** FastAPI + K8s + ArgoCD GitOps
""")

abstract = st.text_area(
    "Paste a PubMed abstract",
    value=SAMPLE_ABSTRACT,
    height=200,
)

if st.button("Classify", disabled=not abstract.strip()):
    with st.spinner("Classifying sentences…"):
        try:
            resp = requests.post(
                f"{API_URL}/predict",
                json={"text": abstract},
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            st.error(f"Error: {exc}")
            st.stop()

    st.markdown("### Result")
    st.caption(f"{len(data['sentences'])} sentences · {data['latency_ms']:.0f} ms")

    for s in data["sentences"]:
        colour = LABEL_COLOURS.get(s["label"], "#888888")
        st.markdown(
            f'<div style="border-left:4px solid {colour};padding:8px 12px;margin:6px 0;'
            f'background:#f8f8f8;border-radius:0 4px 4px 0">'
            f'<span style="background-color:{colour};color:white;padding:1px 6px;'
            f'border-radius:3px;font-size:0.75em;margin-right:8px">{s["label"]}</span>'
            f'<span style="font-size:0.85em">{s["text"]}</span>'
            f'<span style="float:right;color:#aaa;font-size:0.75em">{s["confidence"]:.0%}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
