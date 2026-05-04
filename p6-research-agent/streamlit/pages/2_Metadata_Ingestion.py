import os
import time
import requests
import streamlit as st

API_URL = os.getenv("METADATA_API_URL", "http://metadata-ingestion-metadata-ingestion-api.metadata.svc.cluster.local")

st.set_page_config(page_title="Metadata Ingestion", layout="centered")
st.title("📦 Metadata Ingestion Pipeline")
st.caption("FastAPI → Redis → Celery worker → SHA-256 → Ceph RGW + Postgres")

with st.sidebar:
    st.header("About")
    st.markdown("""
**Pipeline:** HTTP upload → job queued in Redis → Celery worker detects MIME,
computes SHA-256, uploads to Ceph RGW (S3-compatible), writes metadata to Postgres.

**Async pattern:** POST returns 202 immediately with a job ID.
Status is polled until the job reaches `done` or `failed`.

**Infrastructure:** FastAPI + Celery + Redis + Postgres + Ceph RGW · Deployed on K8s
""")

uploaded = st.file_uploader("Upload any file", type=None)

if uploaded and st.button("Ingest"):
    with st.spinner("Submitting…"):
        try:
            resp = requests.post(
                f"{API_URL}/ingest",
                files={"file": (uploaded.name, uploaded.getvalue())},
                timeout=15,
            )
            resp.raise_for_status()
            job_id = resp.json().get("job_id")
        except Exception as exc:
            st.error(f"Error: {exc}")
            st.stop()

    st.info(f"Job queued — ID: `{job_id}`")
    status_box = st.empty()

    for _ in range(30):
        try:
            s = requests.get(f"{API_URL}/status/{job_id}", timeout=5).json()
        except Exception as exc:
            st.error(f"Polling error: {exc}")
            break

        status = s.get("status", "unknown")
        if status == "done":
            status_box.success("✅ Done")
            st.markdown(f"**SHA-256:** `{s.get('sha256','')}`")
            st.markdown(f"**S3 key:** `{s.get('s3_key','')}`")
            st.markdown(f"**MIME type:** `{s.get('mime_type','')}`")
            break
        elif status == "failed":
            status_box.error(f"❌ Failed: {s.get('error_msg','')}")
            break
        else:
            status_box.info(f"Status: **{status}**…")
            time.sleep(2)
