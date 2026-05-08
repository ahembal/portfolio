# Known Issues Register

## Grading system

Each issue is scored on four dimensions (1–5 scale):

| Dimension | 1 | 3 | 5 |
|-----------|---|---|---|
| **Likelihood** | Rare, needs specific trigger | Possible under normal ops | Almost certain to recur |
| **Impact** | Minor inconvenience | Partial service degradation | Full cluster/data outage |
| **Detection** | Immediate alert exists | Detectable with manual check | Silent for days/weeks |
| **Recovery** | Fixed in minutes | Fixed in under an hour | Hours or days to recover |

**Risk score = Likelihood × Impact** (1–25)

> Based on FMEA (Failure Mode and Effects Analysis) — standard engineering
> risk assessment methodology.

---

## Issues

---

### ISS-001 — NTP server IP not updated after MAAS migration

| | |
|---|---|
| **Status** | Resolved — 2026-04-27 |
| **Likelihood** | 4 — Any MAAS IP change silently breaks NTP |
| **Impact** | 5 — Ceph clock skew takes down all OSDs, all PVCs unserviceable |
| **Detection** | 5 — Silent until Ceph health is checked; no alert was firing |
| **Recovery** | 3 — ~2 hours to diagnose and fix clocks + restart daemons |
| **Risk score** | 20 / 25 🔴 |

**What happened:**
MAAS controller IP changed from `192.168.1.87` to `192.168.1.90`. NTP config
on `quick-thrush` and `sought-perch` was written by cloud-init at provision time
and pointed to the old IP. Nodes drifted ~137 seconds over time. Ceph requires
< 0.05s clock skew — monitors marked OSDs down, 100% of placement groups became
inactive, all storage I/O blocked.

**Root cause:** NTP server IP hardcoded in `/etc/systemd/timesyncd.conf.d/cloud-init.conf`.
No alerting on clock skew. No runbook for MAAS IP changes.

**Fix applied:**
- Updated NTP server to `192.168.1.90` on both nodes
- Force-stepped clocks to correct time
- Restarted Ceph monitors and OSDs

**Prevention:**
- `cluster/playbooks/configure-ntp.yml` — idempotent playbook, run after any MAAS IP change
- `cluster/inventory/group_vars/all.yml` — `maas_ntp_server` is now a tracked variable
- TODO: add Prometheus alert on `node_timex_sync_status != 1` (node_exporter metric)

---

### ISS-002 — sought-perch liveness probe failures

| | |
|---|---|
| **Status** | Resolved — 2026-04-28 |
| **Likelihood** | 2 — Requires 7+ days of crash-looping to accumulate corrupt state |
| **Impact** | 4 — All pods on node fail; half the cluster capacity lost |
| **Detection** | 2 — CrashLoopBackOff immediately visible |
| **Recovery** | 3 — Node drain + kubeadm reset + rejoin (~30 minutes) |
| **Risk score** | 8 / 25 🟡 |

**What happened:**
Root cause was `kube-proxy` crash-looping (exit code 2) for 7+ days (14,398
restarts). kube-proxy manages the iptables rules that route traffic to pods.
Without it, HTTP liveness probes from kubelet to pods fail — Kubernetes then
restarts healthy pods, creating the appearance of a node networking bug.

kube-proxy was crashing because 14,000+ partial writes had left the iptables
`KUBE-*` chains in a corrupt/duplicate state it could no longer reconcile.
This was compounded by the NTP clock skew (ISS-001) which caused the initial
kube-proxy failures that started the crash loop.

**Fix:** Drained the node, deleted it from the cluster, ran `kubeadm reset
--force` to wipe all Kubernetes state (iptables, CNI, certs), flushed the
remaining iptables KUBE-* chains and Flannel interfaces manually, then
rejoined with a fresh token. kube-proxy started clean with zero restarts.

**Prevention:**
- Fix clock skew immediately (ISS-001) — prevents initial kube-proxy failures
- Alert on `kube_pod_container_status_restarts_total > 50` for kube-system pods
- If kube-proxy starts crash-looping, don't wait — flush iptables or drain+rejoin early

---

### ISS-003 — Ceph CSI provisioner stale operation locks

| | |
|---|---|
| **Status** | Resolved — 2026-04-27 |
| **Likelihood** | 3 — Occurs when provisioner pod restarts mid-operation |
| **Impact** | 4 — All PVC provisioning blocked until provisioner is restarted |
| **Detection** | 3 — PVCs stay Pending; provisioner logs show "already exists" error |
| **Recovery** | 2 — Force-delete provisioner pod; new pod starts clean |
| **Risk score** | 12 / 25 🟠 |

**What happened:**
Ceph CSI provisioner accumulated stale in-memory operation locks from failed
`CreateVolume` calls (caused by wrong pool name `kubernetes` instead of `k8s-rbd`).
New PVC requests were blocked with "an operation with the given Volume ID already
exists" even after the root cause was fixed.

**Fix:** Force-delete the provisioner pod. The new pod starts with clean state.
```bash
kubectl delete pod -n ceph-csi-rbd <provisioner-pod> --force
```

**Prevention:**
- StorageClass pool name is now documented and committed to git
- `cluster/manifests/ceph-rbd-storageclass.yaml` is the source of truth

---

### ISS-004 — Ceph RBD StorageClass pointing to wrong pool

| | |
|---|---|
| **Status** | Resolved — 2026-04-27 |
| **Likelihood** | 2 — Only occurs on fresh cluster setup without docs |
| **Impact** | 4 — All PVCs fail silently |
| **Detection** | 4 — PVCs Pending with no obvious error; requires reading CSI logs |
| **Recovery** | 1 — Delete and recreate StorageClass with correct pool name |
| **Risk score** | 8 / 25 🟡 |

**What happened:**
StorageClass was created with `pool: kubernetes` (common default in docs) but
the actual Ceph pool is `k8s-rbd`. Every PVC creation silently hung for 13+
minutes before logging a timeout.

**Fix:** StorageClass recreated with `pool: k8s-rbd`.

**Prevention:**
- `cluster/manifests/ceph-rbd-storageclass.yaml` committed to git with correct pool name

---

### ISS-005 — ghcr-pull-secret not propagated to new namespaces

| | |
|---|---|
| **Status** | Open — manual step required |
| **Likelihood** | 5 — Every new project namespace hits this |
| **Impact** | 3 — Pods ImagePullBackOff; service down until secret is copied |
| **Detection** | 2 — ImagePullBackOff is immediately visible |
| **Recovery** | 1 — One kubectl command to copy the secret |
| **Risk score** | 15 / 25 🟠 |

**What happened:**
Kubernetes secrets are namespace-scoped. The `ghcr-pull-secret` exists in `pcam`
but not in `metadata`. Every new project deployment fails with ImagePullBackOff
until the secret is manually copied.

**Workaround:**
```bash
kubectl get secret ghcr-pull-secret -n pcam -o json \
  | jq 'del(.metadata.namespace,.metadata.resourceVersion,.metadata.uid,.metadata.creationTimestamp,.metadata.annotations,.metadata.ownerReferences)' \
  | kubectl apply -f - --namespace <new-namespace>
```

**Long-term fix:** Deploy `reflector` or `kubed` to auto-mirror secrets across
namespaces. Tracked as cluster improvement.

---

### ISS-006 — No dynamic StorageClass (Ceph CSI not fully operational)

| | |
|---|---|
| **Status** | Resolved — 2026-04-28 |
| **Likelihood** | 3 — Any new stateful workload hits this until Ceph is stable |
| **Impact** | 4 — Stateful services (Postgres, Prometheus) cannot start |
| **Detection** | 3 — PVCs stay Pending; requires checking StorageClass and CSI logs |
| **Recovery** | 3 — Requires fixing Ceph cluster health first |
| **Risk score** | 12 / 25 🟠 |

**What happened:**
Cluster had no default StorageClass. Ceph CSI was installed but the StorageClass
was never created. Additionally, sought-perch OSD/provisioner issues left Ceph
in a degraded state that blocked all provisioning.

Root causes identified and fixed:
1. StorageClass pointed to pool `kubernetes` — actual pool name is `k8s-rbd`
2. Ceph provisioner had stale in-memory locks from 12+ hours of failed retries
3. Ceph cluster had 100% inactive PGs due to OSD failures (caused by ISS-001 clock skew)

**Resolution — 2026-04-28:**
- Fixed StorageClass pool name to `k8s-rbd` → committed to `cluster/manifests/ceph-rbd-storageclass.yaml`
- Force-deleted stale provisioner pod to clear in-memory locks
- Fixed NTP (ISS-001) → monitors recovered → OSDs came back → PGs became active
- PVCs now provision correctly via Ceph RBD

**Note on Postgres volumes:** Ceph RBD formats with ext4 which creates a
`lost+found` directory. Postgres refuses to init into a non-empty directory.
Fix: use `subPath: pgdata` in the volumeMount so Postgres gets a clean subdirectory.

**Prevention:**
- `cluster/manifests/ceph-rbd-storageclass.yaml` committed — apply on fresh cluster setup
- Fix NTP (ISS-001) immediately to prevent Ceph OSD failures

---

### ISS-007 — CI pushes full SHA tags but values.yaml stores short SHA

| | |
|---|---|
| **Status** | Resolved — 2026-04-28 |
| **Likelihood** | 5 — Affected every deployment since the pipeline was created |
| **Impact** | 4 — All image pulls fail with NotFound |
| **Detection** | 4 — GHCR returns "not found" — looks like missing image, not tag mismatch |
| **Recovery** | 1 — Update values.yaml with full SHA |
| **Risk score** | 20 / 25 🔴 |

**What happened:**
CI `build-api` and `build-worker` jobs pushed images tagged with the full
40-character commit SHA (`${{ github.sha }}`), e.g.:

```
ghcr.io/ahembal/metadata-api:f523057138174c0fe52b2507ec813644eb8202ce
ghcr.io/ahembal/metadata-api:latest
```

The `update-tags` job wrote only the first 7 characters to `values.yaml`:

```yaml
tag: "f523057"   # ← this tag does not exist in GHCR
```

GHCR does not resolve short SHAs as aliases for full SHAs. When Kubernetes
tried to pull `metadata-api:f523057`, GHCR returned 404 Not Found because
that exact tag was never pushed. Every deployment since CI was created failed
silently — the `latest` tag worked manually but the pinned SHA tag did not.

**Resolution:**
- Changed `update-tags` to write `${GITHUB_SHA}` (full 40-char SHA)
- Updated `values.yaml` manually with the full SHA for the current build
- Fix is in `.github/workflows/p2-ci.yml`

**TODO — better long-term approach:**
Also push an explicit short-SHA tag during the build step so both formats work:
```yaml
tags: |
  ${{ env.API_IMAGE }}:${{ github.sha }}
  ${{ env.API_IMAGE }}:${{ github.sha && substring(0,7) }}
  ${{ env.API_IMAGE }}:latest
```

---

### ISS-009 — kube-proxy exits code 2 on sought-perch after cache sync

| | |
|---|---|
| **Status** | Open — sought-perch cordoned 2026-04-28 |
| **Likelihood** | 5 — Persistent, survives kubeadm reset + rejoin |
| **Impact** | 3 — One worker node unavailable; cluster still functional on quick-thrush + clever-fly |
| **Detection** | 2 — CrashLoopBackOff immediately visible |
| **Recovery** | Unknown — root cause not yet identified |
| **Risk score** | 15 / 25 🟠 |

**What happened:**
After node drain + `kubeadm reset --force` + rejoin (done to fix ISS-002), kube-proxy
started crash-looping again on sought-perch. Same pattern: starts fine, syncs caches,
exits with code 2 after 60–90 seconds with no error logged. Every kube-proxy restart
causes `SandboxChanged` events that kill all other pods on the node (Flannel, Redis,
Postgres etc).

Tried:
- Full iptables flush (filter + nat + mangle)
- kubeadm reset + clean CNI + clean flannel interfaces
- Node drain + delete + rejoin

None fixed it. The crash happens after cache sync with no logged error — the actual
failure is in a goroutine that calls `os.Exit(2)` before logging.

**Workaround:** sought-perch cordoned. All workloads on quick-thrush + clever-fly.

**Investigation TODO:**
1. Get the actual stderr at crash time: `kubectl logs -n kube-system <proxy> --previous | grep -v "^I"`
2. Check for stale IPVS tables: `sudo ipvsadm -L && sudo ipvsadm --clear`
3. Check conntrack table size: `sudo sysctl net.netfilter.nf_conntrack_count`
4. Try running kube-proxy manually with verbose logging: `--v=5`
5. Compare kernel modules between quick-thrush and sought-perch: `lsmod | grep -E "nf_|ip_"`

---

### ISS-010 — CoreDNS forwards to Google 8.8.8.8 (DNS leakage + MITM risk)

| | |
|---|---|
| **Status** | Open — workaround in place, proper fix pending |
| **Likelihood** | 5 — Active now, every external DNS query leaks |
| **Impact** | 3 — Privacy and MITM risk; no immediate service outage |
| **Detection** | 5 — Silent, no alert |
| **Recovery** | 2 — Replace with Unbound, ~30 min |
| **Risk score** | 15 / 25 🟠 |

**What happened:**
MAAS DNS (`192.168.1.90`) intermittently drops packets, causing CoreDNS to fail
external name resolution (`ghcr.io`, `rest.uniprot.org`, `eutils.ncbi.nlm.nih.gov`).
A fallback to `8.8.8.8` was added as a short-term fix to restore service.

**Security weaknesses introduced:**
1. **DNS leakage** — external queries that MAAS can't answer are forwarded to Google.
   Google sees what external services the cluster queries. Also, failed internal hostname
   lookups are forwarded externally, leaking internal naming conventions.
2. **DNS hijacking risk** — if traffic to `8.8.8.8` is intercepted (MITM), an attacker
   could return false IPs for `ghcr.io` or external APIs, redirecting image pulls or
   API calls to malicious endpoints.
3. **No DNSSEC validation** — neither MAAS DNS nor the current CoreDNS config validates
   DNSSEC signatures, making spoofing easier.

**Proper fix — deploy Unbound as a recursive resolver:**

Unbound is a validating, recursive DNS resolver. It resolves external names itself
by walking the DNS hierarchy from root servers — no forwarding to Google required.
Supports DNSSEC validation out of the box.

Deploy as a Kubernetes DaemonSet or as a service on `turtle-mgmt`:

```yaml
# cluster/manifests/unbound.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: unbound
  namespace: kube-system
spec:
  replicas: 2
  selector:
    matchLabels:
      app: unbound
  template:
    spec:
      containers:
      - name: unbound
        image: mvance/unbound:latest
        ports:
        - containerPort: 5335
          protocol: UDP
```

Then update CoreDNS to forward to Unbound instead of MAAS/8.8.8.8:
```
forward . <unbound-service-ip>:5335
```

MAAS DNS remains for internal hostname resolution only — add a separate
zone entry in CoreDNS for the internal domain:
```
homelab.local:53 {
    forward . 192.168.1.90
}
```

**Current state:** `8.8.8.8` fallback active. External DNS works but leaks queries.
Unbound deployment tracked as cluster improvement.

---

## Summary

| ID | Issue | Risk | Status |
|----|-------|------|--------|
| ISS-001 | NTP server IP stale after MAAS migration | 🔴 20 | Resolved |
| ISS-002 | sought-perch liveness probe failures (kube-proxy corrupt iptables) | 🟡 8 | Resolved |
| ISS-003 | Ceph CSI provisioner stale locks | 🟠 12 | Resolved |
| ISS-004 | Ceph StorageClass wrong pool name | 🟡 8 | Resolved |
| ISS-005 | ghcr-pull-secret not propagated to new namespaces | 🟠 15 | Open |
| ISS-006 | No default StorageClass / Ceph not fully operational | 🟠 12 | Resolved |
| ISS-007 | CI pushes full SHA but values.yaml stores short SHA | 🔴 20 | Resolved |
| ISS-010 | CoreDNS forwards to 8.8.8.8 — DNS leakage + MITM risk | 🟠 15 | Open |

**Open items: ISS-005, ISS-009, ISS-010**

---

## Cluster constraints for project development

> As of 2026-04-28. Read this before starting a new project deployment.

**Schedulable nodes:**
- `quick-thrush` — primary worker, 16 CPU / 64 GB RAM, all production workloads
- `clever-fly` — control-plane (un-cordoned), 16 CPU / 64 GB RAM, overflow only

**Do not schedule on:**
- `sought-perch` — cordoned (ISS-009, kube-proxy broken)

**Storage:**
- Default StorageClass: `ceph-rbd` (Ceph RBD, pool `k8s-rbd`)
- Postgres volumes: always use `subPath` in volumeMount (ext4 `lost+found` issue)
- Ceph has 4 active OSDs across 2 hosts — data is replicated 2-way (not 3-way)

**Image pulls:**
- GHCR pull secret must be manually copied to each new namespace (ISS-005)
- Use full SHA tags in Helm values — short SHAs are not pushed to GHCR (ISS-007)
- Token stored in `pass homelab/github/ghcr-pull-token`

**p6 / Ollama:**
- Llama 3.1 8B needs ~16 GB RAM — schedule on quick-thrush (64 GB available)
- Set explicit `resources.requests.memory: 18Gi` on Ollama deployment

**Checklist for new namespace:**
```bash
# 1. Copy pull secret
kubectl get secret ghcr-pull-secret -n pcam -o json \
  | jq 'del(.metadata.namespace,.metadata.resourceVersion,.metadata.uid,.metadata.creationTimestamp,.metadata.annotations,.metadata.ownerReferences)' \
  | kubectl apply -f - --namespace <new-ns>

# 2. Apply sealed secrets if needed
kubectl apply -f k8s/sealed-secret-*.yaml

# 3. Verify Ceph StorageClass exists
kubectl get storageclass ceph-rbd
```
