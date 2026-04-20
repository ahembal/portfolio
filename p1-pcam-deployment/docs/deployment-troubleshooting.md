# Deployment Troubleshooting Log

A record of non-obvious issues encountered building this pipeline and how they were resolved.

---

## 1. ArgoCD NetworkPolicy cascade restart

**Symptom:** After applying ArgoCD manifests, all pods in the `argocd` namespace entered
`CrashLoopBackOff` simultaneously. Logs showed `SandboxChanged` events — the CNI was
rebuilding the pod network sandbox and sending SIGTERM to every pod.

**Root cause:** ArgoCD ships with NetworkPolicies. When applied, the CNI plugin rebuilt the
network sandbox for every running pod in the namespace, issuing SIGTERM to each one. Pods
with short grace periods or liveness probes immediately began crashing, triggering more
restarts in a cascade.

**Fix:** Deleted all 7 ArgoCD NetworkPolicies. Not needed in a homelab environment with no
multi-tenant concerns.

```bash
kubectl delete networkpolicy --all -n argocd
```

---

## 2. dex-server and applicationset-controller unnecessary CrashLoopBackOff

**Symptom:** `argocd-dex-server` and `argocd-applicationset-controller` were in
`CrashLoopBackOff` from the start.

**Root cause:**
- dex-server logs: `"dex is not configured"` → exits 0. Dex handles SSO login. Without an
  SSO provider configured, it exits intentionally on every start.
- applicationset-controller: exit code 143 (SIGTERM on startup). Not needed for single
  application deployments.

**Fix:** Scaled both to 0 replicas — they are optional components for this setup.

```bash
kubectl scale deployment argocd-dex-server --replicas=0 -n argocd
kubectl scale deployment argocd-applicationset-controller --replicas=0 -n argocd
```

---

## 3. Sealed Secrets controller — large CRD annotation limit

**Symptom:** `kubectl apply` on ArgoCD CRDs failed with:
```
The CustomResourceDefinition is invalid: metadata.annotations: Too long, must have at
most 262144 bytes
```

**Root cause:** Client-side apply stores the full manifest as an annotation
(`kubectl.kubernetes.io/last-applied-configuration`) for diffing on the next apply.
Some ArgoCD CRDs exceed the 262 KB annotation limit.

**Fix:** Re-apply using server-side apply, which stores the field manager diff on the
server and does not use the annotation.

```bash
kubectl apply --server-side --force-conflicts -f install.yaml
```

---

## 4. sought-perch node — Flannel crashing every ~7 minutes

**Symptom:** `kube-flannel-ds` pod on `sought-perch` had 11,162+ restarts (exit code 0,
every ~7 minutes). The node was technically Ready but unreliable.

**Root cause:** Suspected kernel VXLAN bug on the older kernel (`6.8.0-101-generic`).
Quick-thrush and clever-fly run `6.8.0-106-generic`. The apt proxy (MAAS Squid at
`192.168.1.90:8000`) did not have `6.8.0-106` cached, blocking the upgrade.

**Workaround:** Drained and cordoned the node (`kubectl drain --ignore-daemonsets
--delete-emptydir-data sought-perch`), continued operating with a 2-node cluster.
Node was later uncordoned after a reboot cleared the Flannel state.

```bash
# Clear Flannel state and reboot
sudo rm -f /run/flannel/subnet.env
sudo reboot
```

---

## 5. ArgoCD repo-server — liveness probe TLS mismatch (v3.x)

**Symptom:** `argocd-repo-server` appeared to start successfully (logs: `"starting grpc
server"`) but exited cleanly (exit code 0) after exactly 12 seconds on every restart,
accumulating 150+ restarts.

**Root cause:** ArgoCD v3 enables TLS on the repo-server by default. The liveness probe
uses a plain gRPC health check (no TLS). The probe fires at `initialDelaySeconds=10`,
fails because TLS is required, and Kubernetes sends SIGTERM — which the server handles
gracefully (exit 0), masking the real cause.

**Fix (step 1):** Patch the repo-server deployment to disable TLS:
```bash
kubectl patch deployment argocd-repo-server -n argocd --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--disable-tls"}]'
```

**Fix (step 2):** Tell the application controller and argocd-server to connect to the
repo-server without TLS (otherwise they get `tls: first record does not look like a TLS
handshake`):
```bash
kubectl patch configmap argocd-cmd-params-cm -n argocd --type=merge \
  -p '{"data":{"reposerver.disable.tls":"true"}}'
kubectl rollout restart deployment/argocd-server deployment/argocd-repo-server -n argocd
```

---

## 6. Ceph RGW — S3 bucket ownership

**Symptom:** Upload to `ml-artifacts` bucket returned `403 Forbidden` with the
`portfolio-manager` user credentials.

**Root cause:** The `ml-artifacts` bucket was created by a different RGW user. In Ceph RGW,
bucket ownership is strict — only the owning user (or an admin) can access a bucket without
an explicit bucket policy grant.

**Fix:** Created a new bucket (`pcam-models`) under the `portfolio-manager` user and
uploaded all artifacts there. Updated `values.yaml` accordingly.

```python
s3.create_bucket(Bucket="pcam-models")
```

---

## 7. CoreDNS → BIND DNS ACL — pods blocked from querying MAAS DNS (by design)

**Symptom:** ArgoCD repo-server returns `lookup github.com: server misbehaving` (SERVFAIL).
CoreDNS logs show HINFO probes to `192.168.1.87` timing out.

**Root cause (two-part):**

Part A — stale IP: The MAAS machine (DNS + HTTP proxy server) moved from `192.168.1.87`
to `192.168.1.90`. The cluster nodes' `systemd-resolved` was still configured (via DHCP)
to query `192.168.1.87`, which no longer serves DNS.

Part B — security design: BIND (`named`) on the MAAS machine is bound only to
`192.168.1.90` and has an ACL that accepts queries only from the LAN subnet
(`192.168.1.0/24`). CoreDNS pods run with IPs in `10.244.x.x` (the Flannel pod network).
These IPs are outside the trusted ACL, so BIND silently drops their queries — by design,
not by accident. This is correct behaviour for a secure environment.

**Correct DNS chain (when working):**
```
CoreDNS pod (10.244.x.x)
  → node's systemd-resolved stub (127.0.0.53)   ← query arrives at node's LAN IP
    → BIND on MAAS (192.168.1.90:53)             ← sees source 192.168.1.x, ACL passes
      → upstream internet DNS
```

**Fix applied (Part A):** Added drop-in config on all nodes to override stale DHCP DNS:
```bash
# /etc/systemd/resolved.conf.d/maas-dns.conf
[Resolve]
DNS=192.168.1.90
```

**Workaround for Part B:** CoreDNS forwards via the node's systemd-resolved stub
(`127.0.0.53`), not directly to BIND. This means queries leave the node via its LAN IP
(`192.168.1.x`), which BIND trusts. The `forward . /etc/resolv.conf` in the Corefile
(with `/etc/resolv.conf` → `127.0.0.53`) is the correct architecture.

**Known remaining issue:** After the MAAS IP change, Tailscale DNS (`100.100.100.100`)
sometimes wins as `Current DNS Server` over the MAAS drop-in, depending on which
interface systemd-resolved considers the default route. This needs a permanent fix via
MAAS DHCP reconfiguration (update the DNS server handed out via DHCP from `.87` to `.90`).

**Deferred:** ArgoCD was deployed via `helm install` (bypassing the GitOps sync) to
unblock progress. The DNS fix will be completed as Step 19 (see PROGRESS.md).

---

## 8. Helm template parse error — `{{if}}` inside YAML comment

**Symptom:** `helm template` and `helm install` fail with:
```
Error: parse error at (pcam-inference/templates/hpa.yaml:47): unexpected EOF
```

**Root cause:** `hpa.yaml` had the following YAML comment on line 12:
```yaml
# The `{{- if .Values.hpa.enabled }}` guard lets you disable HPA for
```

Go's `text/template` engine does not understand YAML comment syntax — `#` is just a
regular character. The `{{- if .Values.hpa.enabled }}` inside the comment was parsed as
a real template action, opening a second `if` block that had no matching `{{- end }}`.
The parser consumed the entire file looking for the closing `end`, hit EOF after
`hpa.yaml`'s last line, and reported the error there.

The error location (`hpa.yaml:47`) was misleading — it pointed to where the parser gave
up, not where the extra `{{if}}` was introduced (line 12 of the same file).

**Fix:** Removed the `{{ }}` delimiters from the comment so the Go template engine
ignores the text:
```diff
-# The `{{- if .Values.hpa.enabled }}` guard lets you disable HPA for
+# The `hpa.enabled` guard lets you disable HPA for
```

**Lesson:** Never write Go template syntax (`{{ }}`) inside YAML comments in Helm
templates — the template engine processes them regardless of the `#` prefix.

**Lesson:** Never write Go template syntax (`{{ }}`) inside YAML comments in Helm
templates — the template engine processes them regardless of the `#` prefix.

---

## 9. Distroless image — CMD must use `-m uvicorn`, not bare `uvicorn`

**Symptom:** Pod crashes immediately with:
```
/usr/bin/python3.11: can't open file '/app/uvicorn': [Errno 2] No such file or directory
```

**Root cause:** `gcr.io/distroless/python3-debian12:nonroot` sets `ENTRYPOINT ["python3.11"]`.
With `CMD ["uvicorn", "main:app", ...]`, the full command becomes `python3.11 uvicorn main:app ...`
— Python tries to open `uvicorn` as a script file, not invoke it as a module.

**Fix:**
```dockerfile
CMD ["-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```
`python3.11 -m uvicorn` tells Python to run uvicorn as an installed module.

---

## 10. Distroless — PyTorch getpwuid() fails for non-existent UID

**Symptom:**
```
KeyError: 'getpwuid(): uid not found: 1000'
```

**Root cause:** PyTorch's inductor cache builder calls `getpass.getuser()` →
`pwd.getpwuid(os.getuid())`. The distroless `nonroot` image only has UID 65532 in
`/etc/passwd`. Deployment was setting `runAsUser: 1000`, which has no passwd entry.

**Fix (two-part):**
1. Change `runAsUser` in deployment.yaml from `1000` to `65532` (distroless nonroot UID).
2. Set `TORCHINDUCTOR_CACHE_DIR: "/tmp/torchinductor"` in the ConfigMap to bypass
   the `getpwuid()` call entirely — PyTorch uses the env var instead of computing it.

---

## 11. Incorrect sys.path in container — parents[2] IndexError

**Symptom:**
```
IndexError: 2 (at Path(__file__).resolve().parents[2])
```

**Root cause:** In the repo, `main.py` lives at `p1-pcam-deployment/serving/main.py`,
so `parents[2]` reaches the repo root. In the container, `main.py` is at `/app/main.py`,
so `parents[0]` = `/app`, `parents[1]` = `/`. `parents[2]` doesn't exist.

The Dockerfile copies `boto3_config.py` to `/app/infra/ceph-rgw/boto3_config.py`,
so the correct in-container path is `Path(__file__).resolve().parent / "infra" / "ceph-rgw"`.

**Fix:**
```python
# Before (repo-relative path, breaks in container)
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "infra" / "ceph-rgw"))

# After (container-relative path)
sys.path.insert(0, str(Path(__file__).resolve().parent / "infra" / "ceph-rgw"))
```

---

## 12. ResNet-18 fc layer shape mismatch — num_classes=2 vs checkpoint num_classes=1

**Symptom:**
```
RuntimeError: Error(s) in loading state_dict for ResNet:
    size mismatch for fc.weight: copying a param with shape torch.Size([1, 512])
    from checkpoint, the shape in current model is torch.Size([2, 512]).
```

**Root cause:** Training used `num_classes=1` (binary BCE: one sigmoid output).
`build_model()` in `main.py` defaulted to `num_classes=2` (CrossEntropyLoss: two outputs).
These are architecturally incompatible.

**Fix:** Changed `build_model` default to `num_classes=1` to match the training setup.

---

## 13. sought-perch Flannel instability causing SandboxChanged SIGTERM loop

**Symptom:** Pod repeatedly starts successfully (model loads, /health 200 OK) then
receives SIGTERM within ~90s. K8s events show:
```
Normal  SandboxChanged  kubelet  Pod sandbox changed, it will be killed and re-created.
Warning Unhealthy       kubelet  Liveness probe failed: context deadline exceeded
```

**Root cause:** sought-perch was still running kernel `6.8.0-101-generic` with the
Flannel VXLAN SIGTERM bug (§4). Flannel periodically crashes and rebuilds the CNI
network sandbox, which sends SIGTERM to all pods running on the node. The node was
rebooted earlier (§4) but the kernel was not upgraded, so Flannel resumed crashing.

**Fix:**
1. Drained sought-perch (`kubectl drain --ignore-daemonsets --delete-emptydir-data sought-perch`)
2. Upgraded kernel: `sudo apt-get install -y linux-image-6.8.0-110-generic linux-modules-6.8.0-110-generic`
3. Cleared stale Flannel state: `sudo rm -f /run/flannel/subnet.env`
4. Rebooted
5. Uncordoned: `kubectl uncordon sought-perch`

sought-perch now runs `6.8.0-110-generic`. Flannel restart count stabilised — no new
restarts observed after kernel upgrade.

**Note:** OSDs 0 and 1 and the sought-perch RGW were already in failed state before
the reboot (likely caused by the same Flannel instability). The pcam service uses
quick-thrush (192.168.1.200) as its RGW endpoint, so this did not affect the deployment.
