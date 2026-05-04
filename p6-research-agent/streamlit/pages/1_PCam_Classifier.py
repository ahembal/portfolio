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
selected_sample = None
for col, (label, fname) in zip(cols, SAMPLES.items()):
    path = DEMO_DIR / fname
    if path.exists():
        col.image(str(path), caption=label, width=96)
        if col.button(f"Use {label}"):
            selected_sample = (label, path.read_bytes())

st.markdown("#### Or upload your own")
uploaded = st.file_uploader(
    "Upload a 96×96 histology patch (JPEG or PNG)",
    type=["jpg", "jpeg", "png"],
)

image_bytes = None
image_name  = None
if selected_sample:
    image_name, image_bytes = selected_sample
    st.image(image_bytes, caption=f"Sample: {image_name}", width=200)
elif uploaded:
    image_bytes = uploaded.getvalue()
    image_name  = uploaded.name
    st.image(image_bytes, caption="Uploaded patch", width=200)

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
