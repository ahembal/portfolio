# Deployment Troubleshooting Log — P6 Research Agent
*Last updated: 2026-05-03*

A record of non-obvious issues encountered deploying this service and how they were resolved.
For cluster-level issues (Ceph, nodes, ArgoCD) see `runbooks/known-issues.md`.

---

## 1. fastapi version conflict with chromadb

**Symptom:** `docker compose build` fails:
```
ERROR: Cannot install fastapi==0.115.12 and chromadb==1.0.7 because these package
versions have conflicting dependencies.
chromadb 1.0.7 depends on fastapi==0.115.9
```

**Root cause:** `requirements.txt` pinned `fastapi==0.115.12` but `chromadb 1.0.7` requires exactly `0.115.9`.

**Fix:** Pin `fastapi==0.115.9` to match chromadb's constraint.

---

## 2. httpx missing from requirements.txt

**Symptom:** API starts locally but `src/api/main.py` fails to import in a clean environment:
```
ModuleNotFoundError: No module named 'httpx'
```

**Root cause:** `main.py` uses `httpx.AsyncClient` for the Ollama health check, but `httpx` was not in `requirements.txt`.

**Fix:** Added `httpx==0.28.1` to `requirements.txt`.

---

## 3. GHCR packages — Actions access must be set before first CI push

**Symptom:** CI `build-api` and `build-streamlit` jobs fail with `403 Forbidden` on push.

**Root cause:** Same as p1 issue §15 — new GHCR packages are private and not linked to the repo. `GITHUB_TOKEN` cannot push to them.

**Fix:** For each new image (`research-agent-api`, `research-agent-streamlit`):
1. Create the package with a dummy push:
```bash
docker tag hello-world ghcr.io/ahembal/research-agent-api:init
docker push ghcr.io/ahembal/research-agent-api:init
```
2. Go to `github.com/users/ahembal/packages/container/<image-name>/settings`
3. **Manage Actions access** → add `portfolio` repository with **Write** access

---

## 4. Ollama model pull on first K8s deployment

**Symptom:** API pod starts but all `/query` requests return 500 — Ollama health check shows `unreachable`.

**Root cause:** On first deployment, the Ollama pod starts but `llama3.1:8b` model weights (~4 GB) have not been pulled yet. The model pull happens inside the container after startup and takes several minutes.

**Fix:** After `helm install`, wait for the model pull before testing:
```bash
kubectl logs -n research-agent deployment/ollama -f | grep "success"
# or poll /health until ollama: "ok"
until curl -s http://<node-ip>:30651/health | grep -q '"ollama":"ok"'; do sleep 10; done
```

Alternatively, pre-pull the model into the PVC by exec-ing into the pod:
```bash
kubectl exec -n research-agent deployment/ollama -- ollama pull llama3.1:8b
```

**Note:** On subsequent restarts the model is already on the PVC — no re-pull needed. This is why the PVC exists.

---

## 5. Ollama scheduling — must run on quick-thrush (64 GB RAM)

**Root cause:** `llama3.1:8b` requires ~16 GB RAM for inference. `clever-fly` does not have enough memory; `sought-perch` is cordoned (ISS-009).

**Fix:** Helm chart sets `nodeSelector: kubernetes.io/hostname: quick-thrush` on the Ollama deployment. Do not remove this selector.

---

## 6. ChromaDB PVC — subPath required

**Root cause:** Ceph RBD volumes formatted as ext4 contain a `lost+found` directory at the root. ChromaDB refuses to initialise in a non-empty directory.

**Fix:** All Ceph RBD volumeMounts use `subPath` in the Helm chart:
```yaml
volumeMounts:
  - name: chromadb-data
    mountPath: /data/chromadb
    subPath: chromadb
```
See ISS-006 in `runbooks/known-issues.md` for full details.

---

## 7. PodSecurity "restricted" violations — missing securityContext

**Symptom:** `helm install` succeeds but warnings appear for all three deployments:
```
would violate PodSecurity "restricted:latest":
  allowPrivilegeEscalation != false
  unrestricted capabilities (must drop ALL)
  runAsNonRoot != true
  seccompProfile not set
```

**Root cause:** The Helm chart templates did not set `securityContext` on pods or containers. The `research-agent` namespace has PodSecurity `restricted:latest` policy enforced by the cluster.

**Fix — api and streamlit deployments:**
- Added pod-level `securityContext`: `runAsNonRoot: true`, `runAsUser: 1000`, `fsGroup: 1000`, `seccompProfile.type: RuntimeDefault`
- Added container-level `securityContext`: `allowPrivilegeEscalation: false`, `capabilities.drop: ["ALL"]`
- Added `USER 1000` to both Dockerfiles — without this, `runAsNonRoot: true` would fail at runtime because the image still defaults to root

**Fix — Ollama deployment:**
- The upstream `ollama/ollama` image mounts models to `/root/.ollama` and runs as root by default
- Set `OLLAMA_MODELS=/models` and `HOME=/models` env vars to redirect the model directory away from `/root`
- Changed `volumeMount.mountPath` to `/models` to match
- Added the same pod and container securityContext as api/streamlit

**Why this matters:**
Running containers as root is a significant attack surface — if the container is compromised, the attacker has root inside the pod and can potentially escape to the node. `capabilities.drop: ALL` and `allowPrivilegeEscalation: false` are baseline hardening required by CIS Kubernetes Benchmark 5.2.x and NIST SP 800-190. The `seccompProfile: RuntimeDefault` enables kernel syscall filtering at no performance cost.

**References:** CIS K8s Benchmark 5.2.3, 5.2.6, 5.2.7 · NIST SP 800-190 §4.4 · ISO 27001:2022 A.8.9
