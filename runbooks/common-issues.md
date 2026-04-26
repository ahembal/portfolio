# Common Issues

## Deploying to the homelab cluster — known constraints

### No dynamic StorageClass

The cluster has no dynamic storage provisioner (no Ceph CSI block, no local-path-provisioner).
PVCs that request a StorageClass will remain `Pending` indefinitely.

**Workaround for stateful services (e.g. Postgres):**
Use a `hostPath` volume pinned to a specific node instead of a PVC.
The pod must also have a `nodeSelector` for that same node so it always
lands where the data is.

```yaml
# In the pod spec:
nodeSelector:
  kubernetes.io/hostname: quick-thrush

volumes:
  - name: pgdata
    hostPath:
      path: /data/metadata-postgres
      type: DirectoryOrCreate
```

**Long-term fix:** Install `local-path-provisioner` (Rancher) — a lightweight
StorageClass that provisions `hostPath` volumes automatically from a node-local
directory. One-liner install:
```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/master/deploy/local-path-storage.yaml
```
After install, set it as the default StorageClass and remove all manual `hostPath` workarounds.
Tracked as a cluster improvement task.

---

### `ghcr-pull-secret` must exist in every namespace

The GHCR pull secret is namespace-scoped in Kubernetes — it must exist in
every namespace that pulls private images. It is not shared automatically.

**When deploying a new project to a new namespace**, copy the secret:
```bash
kubectl get secret ghcr-pull-secret -n pcam -o json \
  | jq 'del(.metadata.namespace,.metadata.resourceVersion,.metadata.uid,.metadata.creationTimestamp,.metadata.annotations,.metadata.ownerReferences)' \
  | kubectl apply -f - --namespace <new-namespace>
```

**Long-term fix:** Use a tool like `reflector` or `kubed` to automatically
mirror secrets across namespaces. Tracked as a cluster improvement task.

---

### All pods scheduled to `sought-perch`

The Kubernetes scheduler places pods on any available node by default.
`sought-perch` has intermittent liveness probe failures (see cluster/README.md).
Without a `nodeSelector`, workloads land there and appear to fail for
unrelated reasons (ImagePullBackOff, CrashLoopBackOff).

**Fix for every new workload:** Add `nodeSelector: quick-thrush` to the
Helm chart until `sought-perch` is confirmed stable.

```yaml
# In values.yaml or deployment templates:
nodeSelector:
  kubernetes.io/hostname: quick-thrush
```

---

## git pull / git fetch stalls silently

**Symptom:** `git pull` or `git fetch` hangs indefinitely with no output.

**Cause:** A stale SSH multiplexer socket from a previous session.
Git reuses an existing SSH connection via `~/.ssh/socket-git@github.com-22`.
If that session died uncleanly the socket file still exists but the connection
is broken, so git waits forever for a response that never comes.

**Fix:**
```bash
ssh -O exit git@github.com
```

This sends the `exit` command to the SSH master process, closing the socket
cleanly. Then `git pull` / `git fetch` will open a fresh connection.

**If that doesn't work** (socket file exists but process is already dead):
```bash
rm -f ~/.ssh/socket-git@github.com-22
```

**Prevention:** The SSH config in `~/.ssh/config` controls multiplexing.
If this recurs often, reduce `ControlPersist` from its current value or
disable multiplexing for GitHub entirely:
```
Host github.com
    ControlMaster no
```
