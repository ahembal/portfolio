import io
import os
from pathlib import Path

import requests
import streamlit as st
from PIL import Image

API_URL = os.getenv("PCAM_API_URL", "http://pcam-pcam-inference.pcam.svc.cluster.local")

DEMO_DIR = Path(__file__).parent.parent / "demo"
SAMPLES = {
    "Normal (1)": "normal_1.png",
    "Normal (2)": "normal_2.png",
    "Tumour (1)": "tumour_1.png",
    "Tumour (2)": "tumour_2.png",
}

st.set_page_config(page_title="PCam Classifier", layout="centered")
st.title("🔬 PCam Histology Classifier")
st.caption("ResNet-18 · AUC 0.97 · Trained on PatchCamelyon · Deployed via K8s + ArgoCD")

with st.sidebar:
    st.header("About")
    st.markdown("""
**Model:** ResNet-18 fine-tuned on PatchCamelyon (96×96 histology patches).

**Task:** Binary classification — does the patch contain metastatic tumour tissue?

**Metrics:** AUC 0.9657 · Accuracy 90.0% · F1 0.897

**Infrastructure:** FastAPI + distroless container + Helm chart + ArgoCD GitOps
""")

st.markdown("#### Try a sample patch")
cols = st.columns(len(SAMPLES))
for col, (label, fname) in zip(cols, SAMPLES.items()):
    path = DEMO_DIR / fname
    if path.exists():
        col.image(str(path), caption=label, width=96)
        if col.button(f"Use {label}"):
            st.session_state["image_bytes"] = path.read_bytes()
            st.session_state["image_name"]  = fname

st.markdown("#### Or upload your own")
uploaded = st.file_uploader(
    "Upload a 96×96 histology patch (JPEG or PNG)",
    type=["jpg", "jpeg", "png"],
)
if uploaded:
    st.session_state["image_bytes"] = uploaded.getvalue()
    st.session_state["image_name"]  = uploaded.name

image_bytes = st.session_state.get("image_bytes")
image_name  = st.session_state.get("image_name", "patch.png")
if image_bytes:
    st.image(image_bytes, caption=image_name, width=200)

if image_bytes and st.button("Classify"):
        with st.spinner("Running inference…"):
            try:
                resp = requests.post(
                    f"{API_URL}/predict",
                    files={"file": (image_name, image_bytes, "image/png")},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                st.error(f"Error: {exc}")
                st.stop()

        label = data.get("label", "unknown")
        conf  = data.get("confidence", 0.0)
        latency = data.get("latency_ms", 0.0)

        if label == "tumour":
            st.error(f"🔴 **Tumour** — confidence {conf:.1%}")
        else:
            st.success(f"🟢 **Normal** — confidence {conf:.1%}")

        st.caption(f"Latency: {latency:.1f} ms")
