# Kubernetes Issues Log
*p1-pcam-deployment — cluster and infrastructure issues*

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

**Workaround:** Drained and cordoned the node, continued operating with a 2-node cluster.
Node was later uncordoned after a reboot cleared the Flannel state.

```bash
sudo rm -f /run/flannel/subnet.env
sudo reboot
```

---

## 5. ArgoCD repo-server — liveness probe TLS mismatch (v3.x)

**Symptom:** `argocd-repo-server` appeared to start successfully but exited cleanly
(exit code 0) after exactly 12 seconds on every restart, accumulating 150+ restarts.

**Root cause:** ArgoCD v3 enables TLS on the repo-server by default. The liveness probe
uses a plain gRPC health check (no TLS). The probe fires at `initialDelaySeconds=10`,
fails because TLS is required, and Kubernetes sends SIGTERM — which the server handles
gracefully (exit 0), masking the real cause.

**Fix:**
```bash
kubectl patch deployment argocd-repo-server -n argocd --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--disable-tls"}]'

kubectl patch configmap argocd-cmd-params-cm -n argocd --type=merge \
  -p '{"data":{"reposerver.disable.tls":"true"}}'
kubectl rollout restart deployment/argocd-server deployment/argocd-repo-server -n argocd
```

---

## 6. Ceph RGW — S3 bucket ownership

**Symptom:** Upload to `ml-artifacts` bucket returned `403 Forbidden`.

**Root cause:** The bucket was created by a different RGW user. In Ceph RGW, bucket
ownership is strict — only the owning user (or an admin) can access a bucket without
an explicit bucket policy grant.

**Fix:** Created a new bucket (`pcam-models`) under the `portfolio-manager` user.

```python
s3.create_bucket(Bucket="pcam-models")
```

---

## 7. CoreDNS → BIND DNS ACL — pods blocked from querying MAAS DNS

**Symptom:** ArgoCD repo-server returns `lookup github.com: server misbehaving` (SERVFAIL).

**Root cause (two-part):**

Part A — stale IP: MAAS moved from `192.168.1.87` to `192.168.1.90`. Nodes still
queried the old IP.

Part B — security design: BIND on MAAS only accepts queries from the LAN subnet
(`192.168.1.0/24`). CoreDNS pods run with IPs in `10.244.x.x` — outside the trusted
ACL, so BIND silently drops their queries.

**Correct DNS chain:**
```
CoreDNS pod (10.244.x.x)
  → node's systemd-resolved stub (127.0.0.53)   ← query arrives at node's LAN IP
    → BIND on MAAS (192.168.1.90:53)             ← sees source 192.168.1.x, ACL passes
```

**Fix:** Added drop-in config on all nodes:
```bash
# /etc/systemd/resolved.conf.d/maas-dns.conf
[Resolve]
DNS=192.168.1.90
```

---

## 8. sought-perch Flannel instability causing SandboxChanged SIGTERM loop

**Symptom:** Pod repeatedly starts successfully then receives SIGTERM within ~90s.
K8s events show `SandboxChanged` — CNI rebuilding network sandbox.

**Root cause:** sought-perch still running kernel `6.8.0-101-generic` with the Flannel
VXLAN SIGTERM bug.

**Fix:**
```bash
kubectl drain --ignore-daemonsets --delete-emptydir-data sought-perch
sudo apt-get install -y linux-image-6.8.0-110-generic linux-modules-6.8.0-110-generic
sudo rm -f /run/flannel/subnet.env
sudo reboot
kubectl uncordon sought-perch
```

---

## 9. metrics-server — kubelet TLS SAN mismatch

**Symptom:** `kubectl top nodes` returns `ServiceUnavailable`. metrics-server logs:
```
tls: failed to verify certificate: x509: cannot validate certificate for 192.168.1.200
because it doesn't contain any IP SANs
```

**Root cause:** Kubelet serving certificates were generated without IP SANs for node LAN IPs.

**Workaround (homelab):**
```bash
kubectl patch deployment metrics-server -n kube-system --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-",
        "value":"--kubelet-insecure-tls"}]'
```

**Known risk:** Disables certificate verification between metrics-server and kubelets.
Acceptable for homelab; not acceptable in production.
