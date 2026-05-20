# Security & Production Readiness
*p9 — Knowledge Graph & Semantic Search*

---

## Current security posture

### Non-root container

The Fuseki process runs as UID 100 / GID 101 (`fuseki` user inside the
`stain/jena-fuseki` image). It never runs as root.

The pod-level `securityContext.fsGroup: 101` ensures the ceph-rbd PVC mounted
at `/fuseki/databases` is group-owned by the fuseki group before any container
starts. This is preferable to running an initContainer as root (`runAsUser: 0`)
to `chown` the directory — `fsGroup` is a Kubernetes-native mechanism that
achieves the same result without ever elevating privileges.

### Credentials

RGW credentials (endpoint, access-key, secret-key) are injected from the
`p9-rgw-credentials` Kubernetes Secret. They are never stored in `values.yaml`
or any committed file. The Secret is created out-of-band before deployment:

```
kubectl create secret generic p9-rgw-credentials \
  --from-literal=endpoint=http://<rgw-ip> \
  --from-literal=access-key=<KEY> \
  --from-literal=secret-key=<SECRET> \
  -n knowledge-graph
```

### Network exposure

Fuseki is exposed as a NodePort on port 30900. This makes the SPARQL endpoint
reachable from within the homelab network. It is not exposed to the public
internet — the cluster nodes are behind NAT.

The SPARQL endpoint has no authentication in the current deployment. The Fuseki
admin interface (password set via `ADMIN_PASSWORD` env var) is available but
the SPARQL query endpoint itself is unauthenticated. This is acceptable for a
homelab demo on a private network; see production readiness below.

### Data at rest

The TDB2 database lives on a ceph-rbd PVC. Ceph does not encrypt data at rest
by default in this homelab setup. Encryption at rest would require enabling
Ceph's `ceph-bluestore-encryption` or using a Kubernetes CSI encryption layer.

---

## Deployment strategy

Fuseki uses `strategy: Recreate` rather than the Kubernetes default
`RollingUpdate`. This is required because TDB2 (Fuseki's on-disk storage) uses
an exclusive file lock (`tdb.lock`). If two Fuseki pods were running
simultaneously sharing the same PVC, the second pod would fail immediately with:

```
Failed to get a lock: file='/fuseki/databases/p9/tdb.lock': held by process N
```

`Recreate` terminates the old pod before starting the new one, accepting a
brief downtime window during upgrades in exchange for data integrity.

**Trade-off:** `RollingUpdate` gives zero-downtime deployments for stateless
services, but breaks for any service that holds an exclusive resource lock.
Databases, message brokers, and search indexes with single-writer semantics all
have this constraint.

---

## Production readiness

Items that would need to be addressed before running this in production:

| # | Item | Current state | Production requirement |
|---|------|--------------|----------------------|
| 1 | Deployment strategy | `Recreate` (brief downtime on upgrade) | Migrate to `StatefulSet` with application-level HA for zero-downtime upgrades |
| 2 | SPARQL authentication | None — endpoint is open | Add Fuseki shiro.ini ACL or put an auth proxy (OAuth2-proxy, Keycloak) in front |
| 3 | Data encryption at rest | None — ceph-rbd unencrypted | Enable Ceph BlueStore encryption or CSI-level encryption |
| 4 | TLS | None — plain HTTP on port 3030/30900 | Terminate TLS at an Ingress with cert-manager |
| 5 | Backup | None | Periodic TDB2 dump to RGW or Ceph snapshot |
| 6 | Resource limits | Conservative (1Gi memory) | Profile under real query load; TDB2 caches aggressively |
| 7 | Graph refresh | Manual (re-run builder Job) | Schedule builder Job on a cron to keep graph current |
