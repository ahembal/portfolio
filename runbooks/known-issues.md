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
| **Status** | Open — workaround in place |
| **Likelihood** | 5 — Ongoing, every workload scheduled there is affected |
| **Impact** | 3 — Pods on sought-perch crash-loop; workloads on other nodes unaffected |
| **Detection** | 2 — CrashLoopBackOff is visible in kubectl immediately |
| **Recovery** | 2 — Add nodeSelector to avoid the node; 5 minutes |
| **Risk score** | 15 / 25 🟠 |

**What happened:**
Pods scheduled on `sought-perch` have their liveness probes fail intermittently,
causing Kubernetes to restart healthy pods (exit code 0). Affects: sealed-secrets
controller, ArgoCD pods, Ceph CSI provisioner, Redis.

**Suspected cause:** Residual Flannel VXLAN networking issue after kernel upgrade
from 6.8.0-101 (confirmed buggy) to 6.8.0-110. Pod network MTU or NIC driver
issue causing HTTP health check packets to be dropped.

**Workaround:** `nodeSelector: kubernetes.io/hostname: quick-thrush` on all
critical workloads.

**Investigation steps (TODO):**
1. Check Flannel MTU: `kubectl exec -n kube-flannel <pod-on-sought-perch> -- cat /run/flannel/subnet.env`
2. Compare NIC MTU: `ip link show` on sought-perch vs quick-thrush
3. Check dropped packets: `netstat -s | grep retransmit` on sought-perch
4. If MTU mismatch: patch Flannel ConfigMap with explicit `"MTU": 1450`
5. After fix: remove all nodeSelector pins

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
| **Status** | Partially resolved — StorageClass created, PVC provisioning being tested |
| **Likelihood** | 3 — Any new stateful workload hits this until Ceph is stable |
| **Impact** | 4 — Stateful services (Postgres, Prometheus) cannot start |
| **Detection** | 3 — PVCs stay Pending; requires checking StorageClass and CSI logs |
| **Recovery** | 3 — Requires fixing Ceph cluster health first |
| **Risk score** | 12 / 25 🟠 |

**What happened:**
Cluster had no default StorageClass. Ceph CSI was installed but the StorageClass
was never created. Additionally, sought-perch OSD/provisioner issues left Ceph
in a degraded state that blocked all provisioning.

**Fix in progress:** Ceph cluster being recovered (ISS-001 clock skew fix).
Once OSDs are back, StorageClass `ceph-rbd` should provision PVCs correctly.

**Prevention:**
- `cluster/manifests/ceph-rbd-storageclass.yaml` committed — apply on fresh cluster setup

---

## Summary

| ID | Issue | Risk | Status |
|----|-------|------|--------|
| ISS-001 | NTP server IP stale after MAAS migration | 🔴 20 | Resolved |
| ISS-002 | sought-perch liveness probe failures | 🟠 15 | Open |
| ISS-003 | Ceph CSI provisioner stale locks | 🟠 12 | Resolved |
| ISS-004 | Ceph StorageClass wrong pool name | 🟡 8 | Resolved |
| ISS-005 | ghcr-pull-secret not propagated | 🟠 15 | Open |
| ISS-006 | No default StorageClass | 🟠 12 | Partial |

**Open high-risk items: ISS-002, ISS-005**
