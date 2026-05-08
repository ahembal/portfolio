# Access Runbook
*How to connect to external and internal systems used by this portfolio.*

Credentials and IPs are stored locally in `.env` at the repo root — never committed.

---

## Ceph RGW Object Store

**What:** S3-compatible object store. Hosts ML model artifacts (p1, p4) and dataset storage.

**Where:** Runs as a standalone process on `quick-thrush` (primary worker node), not inside Kubernetes.
Accessible on the local network or via Tailscale. IPs in `.env` as `RGW_ENDPOINT`.

**Connect with s3cmd:**
```bash
source .env
s3cmd --host=<RGW_ENDPOINT> \
      --host-bucket="<RGW_ENDPOINT>/%(bucket)" \
      --access_key=$RGW_ACCESS_KEY \
      --secret_key=$RGW_SECRET_KEY \
      --no-ssl \
      ls s3://
```

**Common operations:**
```bash
# List bucket contents
s3cmd ... ls s3://nlp-models/pubmed-rct/v1/

# Delete files recursively
s3cmd ... del s3://nlp-models/pubmed-rct/v1/.cache/ --recursive
```

---

## MAAS

**What:** Metal as a Service — manages bare metal node provisioning and networking.

**Where:** Runs on `turtle-mgmt`. Access via Tailscale or local network. URL and API key in `.env` as `MAAS_API_URL` / `MAAS_API_KEY`.

---

## Kubernetes Cluster

**Contexts:**

| Context | When to use |
|---------|-------------|
| `emre@homelab-tailscale` | Normal use — connects via Tailscale |
| `emre@homelab` | Requires SSH tunnel to localhost |

**Switch context:**
```bash
kubectl config use-context emre@homelab-tailscale
```

**Note:** `emre@homelab-tailscale` uses `insecure-skip-tls-verify` — Tailscale IP not yet added to API server cert SANs (see known-issues.md).

---

## GitHub / git push

SSH config uses multiplexing (`ControlMaster`). If `git push` hangs or authenticates
as the wrong user (e.g. `aut-mujx` instead of `ahembal`), a stale master socket is
the cause. Fix:

```bash
ssh -O exit git@github.com   # kill the stale master socket
git push                      # retries with a fresh connection
```

The socket files live in `~/.ssh/` — look for entries matching `github.com`.
