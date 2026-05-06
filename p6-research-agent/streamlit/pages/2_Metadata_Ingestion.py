import os
import time

import requests
import streamlit as st

API_URL = os.getenv(
    "METADATA_API_URL",
    "http://metadata-ingestion-metadata-ingestion-api.metadata.svc.cluster.local",
)

st.set_page_config(page_title="Metadata Ingestion", layout="wide")
st.title("📦 Metadata Ingestion Pipeline")
st.caption("FastAPI · Redis · Celery · SHA-256 · Ceph RGW · Postgres")

with st.sidebar:
    st.header("What this demonstrates")
    st.markdown("""
**The problem:** Uploading a file and processing it synchronously blocks the HTTP
connection. For large files or slow processing, this times out.

**The solution:** Async pipeline.

1. `POST /ingest` returns **202 Accepted** immediately with a job ID
2. The job is placed in **Redis** (job queue)
3. A **Celery worker** picks it up and:
   - Detects the MIME type from raw bytes
   - Computes **SHA-256** (content fingerprint)
   - Uploads to **Ceph RGW** (S3-compatible object storage)
   - Writes metadata to **Postgres**
4. The client polls `/status/{id}` until done

**Why it matters:** The API stays responsive at all times.
Multiple workers can process jobs in parallel. Queue depth is
visible in Prometheus for autoscaling.
""")

st.markdown("---")
col1, col2 = st.columns([1, 1])

with col1:
    st.markdown("### Upload a file")
    uploaded = st.file_uploader("Any file type accepted", type=None)

    if uploaded and st.button("Ingest →", type="primary"):
        with st.spinner("Submitting to pipeline…"):
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

        st.info(f"**202 Accepted** — job ID: `{job_id}`")
        st.caption("The file is now in the Redis queue. Polling for status…")

        status_placeholder = st.empty()
        result_placeholder = st.empty()

        for i in range(30):
            try:
                s = requests.get(f"{API_URL}/status/{job_id}", timeout=5).json()
            except Exception as exc:
                st.error(f"Polling error: {exc}")
                break

            status = s.get("status", "unknown")
            status_placeholder.info(f"**{status.upper()}** — step {i+1}/30…")

            if status == "done":
                status_placeholder.success("✅ Pipeline complete")
                with result_placeholder.container():
                    st.markdown("### Result")
                    st.markdown(
                        f"**SHA-256** (content fingerprint):\n`{s.get('sha256','')}`"
                    )
                    st.markdown(
                        f"**S3 key** (location in Ceph RGW):\n`{s.get('s3_key','')}`"
                    )
                    st.markdown(f"**MIME type:** `{s.get('mime_type','')}`")
                    st.markdown(f"**File size:** {s.get('size_bytes', '—')} bytes")
                    st.caption(
                        "The file is now stored in Ceph RGW. The SHA-256 can be used "
                        "to verify integrity or detect duplicates. The metadata "
                        "(job_id, sha256, s3_key, mime_type, timestamps) is in Postgres."
                    )
                break
            elif status == "failed":
                status_placeholder.error(f"❌ Failed: {s.get('error_msg', 'unknown error')}")
                break
            else:
                time.sleep(2)

with col2:
    st.markdown("### Pipeline flow")
    st.markdown("""
```
Your browser
     │
     │  POST /ingest  (multipart file)
     ▼
FastAPI  ─── returns 202 + job_id immediately
     │
     │  enqueue(job_id, filename)
     ▼
Redis  (job queue)
     │
     │  worker picks up job
     ▼
Celery Worker
  ├─ detect MIME type from bytes
  ├─ compute SHA-256
  ├─ upload → Ceph RGW (S3)
  │     bucket: uploads/
  │     key: yyyy/mm/dd/{job_id}/{filename}
  └─ write metadata → Postgres
          status: done
          sha256: abc123…
          s3_key: uploads/…
          mime_type: image/jpeg

Browser polls GET /status/{job_id}
     │
     └─ returns {status, sha256, s3_key, …}
```
""")
