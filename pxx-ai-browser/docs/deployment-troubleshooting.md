# Deployment Troubleshooting
*p11 — AI Developer Browser*

---

## Pre-deploy checklist

1. p6 (`research-agent` namespace) is deployed and healthy
2. `ghcr-pull-secret` is copied into the `ai-browser` namespace
3. `quick-thrush` is schedulable (Ollama lives there)

```bash
# Verify p6 is up
kubectl get pods -n research-agent

# Copy pull secret
kubectl get secret ghcr-pull-secret -n research-agent -o yaml \
  | sed 's/namespace: research-agent/namespace: ai-browser/' \
  | kubectl apply -f -
```

---

## Backend pod stuck in CrashLoopBackOff

**Check logs first:**
```bash
kubectl logs -n ai-browser -l app=ai-browser-backend --previous
```

**Common causes:**

| Symptom in logs | Cause | Fix |
|----------------|-------|-----|
| `Connection refused` to p6 URL | p6 not deployed or wrong DNS | Verify p6 is up; check `P6_RESEARCH_AGENT_URL` in values.yaml |
| `Connection refused` to Ollama | Ollama pod not ready | Wait for Ollama to finish model load; check `kubectl get pods -n research-agent` |
| `ModuleNotFoundError` | Image built without `pip install -e .` | Rebuild image; check Dockerfile COPY order |
| OOMKilled (exit code 137) | Memory limit too low during startup | Increase `resources.limits.memory` in values.yaml |

---

## Research companion returns error immediately

The research companion proxies to p6. If p6 is degraded, all research requests
fail. Check p6 health first:

```bash
curl http://100.82.75.34:<p6-api-nodeport>/health
```

If p6 is healthy but the proxy still fails, check that cross-namespace DNS
resolves from the ai-browser namespace:

```bash
kubectl run -n ai-browser -it --rm debug --image=curlimages/curl --restart=Never \
  -- curl http://research-agent-api.research-agent.svc.cluster.local:8000/health
```

---

## Docs companion gives empty or nonsensical answers

**Cause:** Page content not reaching the backend, or truncated.

The renderer calls `webview.executeJavaScript("document.body.innerText.slice(0,8000)")`.
If the page uses shadow DOM or heavy JS rendering, `innerText` may be empty.

**Check:** Open DevTools in the Electron renderer and run:
```js
document.body.innerText.slice(0, 200)
```
If empty, the page is JS-rendered. The `fetch_page_text` tool will also return
empty content from httpx for the same reason — this is a known limitation.
See PROGRESS.md F2 (Playwright fallback).

---

## Webview shows blank page for some URLs

Electron's webview CSP override covers most cases. If a specific site still
fails, check the devtools Console in the webview for errors.

For sites served over HTTP (not HTTPS), Electron may block mixed content.
The address bar normalises input to `https://` by default — override by
typing the full `http://` URL explicitly.

---

## Electron app cannot reach local backend

When running the Electron app in development (`npm run dev`), the backend
URL defaults to `http://localhost:8001`. The backend must be running locally:

```bash
cd p11-ai-browser/backend
pip install -e .
P6_RESEARCH_AGENT_URL=http://<cluster-ip>:<p6-nodeport> \
  uvicorn src.api.main:app --port 8001
```

If the cluster is not accessible locally, use port-forward for p6:
```bash
kubectl port-forward -n research-agent svc/research-agent-api 8000:8000
```
Then set `P6_RESEARCH_AGENT_URL=http://localhost:8000`.

---

## ArgoCD sync fails

```bash
kubectl describe application ai-browser -n argocd
```

Common causes:
- Helm template error — run `helm template helm/ai-browser/` locally to verify
- `ai-browser` namespace not created — the namespace template in the chart
  creates it; if the Application CR itself fails before namespace creation,
  create it manually: `kubectl create namespace ai-browser`
