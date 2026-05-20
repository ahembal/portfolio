# Deployment Troubleshooting
*p9 — Knowledge Graph & Semantic Search*

---

## Issue 1 — Wrong Fuseki image tag

**Symptom:**
```
Failed to pull image "apache/jena-fuseki:4.10.0": pull access denied,
repository does not exist or may require authorization
```

**Cause:** `apache/jena-fuseki` does not exist on Docker Hub. Apache does not
publish an official ready-to-pull image. The commonly used community image is
`stain/jena-fuseki`, maintained by Stian Soiland-Reyes (a contributor to
Apache Jena). The latest available tag at time of deployment was `4.8.0`.

**Fix:** Set `image.repository: stain/jena-fuseki` and `image.tag: 4.8.0` in
`helm/values.yaml`.

**Note:** `stain/jena-fuseki` is not the official Apache image — it is
community-maintained. For production, consider building from the official
`org.apache.jena:jena-fuseki-docker` Maven package.

---

## Issue 2 — Fuseki entrypoint `illegal option --`

**Symptom:**
```
/docker-entrypoint.sh: exec: line 49: illegal option --
```

**Cause:** The `stain/jena-fuseki` entrypoint script at line 49 does:
```bash
exec "$@" &
```
It passes `$@` directly as the command to execute. The Docker `CMD` is
`["/jena-fuseki/fuseki-server"]` which provides the binary. When Kubernetes
`args` override the CMD, `$@` becomes only the args (e.g. `--update /p9`)
with no binary prefix — so the script tries to execute `--update` as a
command, which fails.

**Fix:** Do not override `args` in the Helm chart. Let the default CMD
(`/jena-fuseki/fuseki-server`) pass through as `$@`. Configure the dataset
via a `config.ttl` file mounted at `/fuseki/config.ttl` (Fuseki's default
config location) using a ConfigMap with `subPath`.

---

## Issue 3 — `/fuseki/databases` not writable

**Symptom:**
```
org.apache.jena.fuseki.FusekiConfigException: Not writable: /fuseki/databases
```

**Cause:** The ceph-rbd PVC is mounted with root ownership. Fuseki runs as
UID 100 / GID 101 and cannot write to a root-owned directory.

**Fix:** Set `securityContext.fsGroup: 101` at the pod level. Kubernetes
applies the group ownership to all mounted volumes before any container starts,
so `/fuseki/databases` is group-writable by the fuseki user when Fuseki starts.

An earlier attempt used an initContainer running as root (`runAsUser: 0`) to
`chown -R 100:101 /fuseki/databases`. This works but is less clean — it
requires a privileged initContainer. `fsGroup` achieves the same result
without elevated privileges.

---

## Issue 4 — TDB2 lock conflict on rolling update

**Symptom:**
```
Failed to get a lock: file='/fuseki/databases/p9/tdb.lock': held by process N
```

**Cause:** Kubernetes default deployment strategy is `RollingUpdate` — it
starts a new pod before terminating the old one. TDB2 uses an exclusive file
lock to prevent concurrent writes. The new pod cannot acquire the lock while
the old pod is still running and holding it.

**Fix:** Set `strategy.type: Recreate` in the Deployment. This terminates the
old pod before starting the new one, accepting a brief downtime window during
upgrades. See `docs/security.md` — production readiness item 1 for the
long-term mitigation (StatefulSet with HA).
