# turtle-mgmt — Storage & Infrastructure Node

`turtle-mgmt` is the homelab's infrastructure controller. It runs MAAS (bare metal
provisioning) and hosts the Ceph cluster that provides storage to Kubernetes.

---

## Storage architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Ceph cluster (managed by ceph orch, runs on bare metal)    │
│                                                             │
│  Daemons spread across nodes:                               │
│                                                             │
│  quick-thrush   ── MON, OSD ──┐                             │
│  sought-perch   ── MON, OSD ──┤── Ceph RADOS (object store)│
│  alert-lizard   ── MON, OSD ──┘                             │
│                                                             │
│  quick-thrush   ── RGW (Ceph Object Gateway) ───────────►  │
│                    port 80, LAN IP                          │
└─────────────────────────────────────────────────────────────┘
              │                        │
              │ Block storage           │ Object storage (S3-compatible)
              ▼                        ▼
┌─────────────────────┐    ┌────────────────────────────┐
│  ceph-csi-rbd       │    │  s3cmd / boto3             │
│  (in Kubernetes)    │    │  (from any node or laptop) │
│                     │    │                            │
│  PVCs → RBD volumes │    │  s3://nlp-models/...       │
│  (Postgres, Prom)   │    │  s3://pcam-models/...      │
└─────────────────────┘    └────────────────────────────┘
```

---

## Two storage paths

| Path | What | How accessed | Used by |
|------|------|--------------|---------|
| Block (RBD) | Persistent volumes for stateful K8s workloads | `ceph-csi-rbd` StorageClass inside K8s | Postgres, Prometheus, Redis |
| Object (RGW) | S3-compatible bucket storage for large files | HTTP on port 80 (LAN) via s3cmd or boto3 | ML model artifacts (p1, p4) |

The RGW is **not** a Kubernetes service — it is a Ceph daemon running directly on
`quick-thrush` managed by `ceph orch`. There is no `kubectl get svc` entry for it.
This is intentional: object storage does not need to be inside Kubernetes, and keeping
it as a Ceph daemon means it is managed alongside the rest of the Ceph cluster.

---

## MAAS

MAAS runs on `turtle-mgmt` and handles:
- Bare metal provisioning of cluster nodes (PXE boot, OS install via cloud-init)
- DNS for the internal network (nodes resolve each other by hostname)
- NTP server for the cluster — **must be updated if turtle-mgmt IP changes** (see ISS-001)

Connection: Tailscale or LAN. Credentials in `.env` (`MAAS_API_URL`, `MAAS_API_KEY`).

---

## Key operational notes

- If the MAAS IP changes, update NTP config on all nodes immediately — Ceph requires < 0.05s clock skew (ISS-001)
- RGW credentials are in `.env` (`RGW_ACCESS_KEY`, `RGW_SECRET_KEY`)
- The Ceph pool for K8s block storage is `k8s-rbd` — not `kubernetes` (ISS-004)
- Ceph replication factor is 2 (data on 2 of 3 nodes) — losing 2 nodes loses data
