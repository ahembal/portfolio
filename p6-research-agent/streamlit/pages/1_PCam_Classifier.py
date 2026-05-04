import os
import requests
import streamlit as st

API_URL = os.getenv("PCAM_API_URL", "http://pcam-pcam-inference.pcam.svc.cluster.local")

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

uploaded = st.file_uploader(
    "Upload a 96×96 histology patch (JPEG or PNG)",
    type=["jpg", "jpeg", "png"],
)

if uploaded:
    st.image(uploaded, caption="Uploaded patch", width=200)
    if st.button("Classify"):
        with st.spinner("Running inference…"):
            try:
                resp = requests.post(
                    f"{API_URL}/predict",
                    files={"file": (uploaded.name, uploaded.getvalue(), uploaded.type)},
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
