# Common Issues

## CI/CD — git push pattern for values.yaml tag updates

All project CI workflows (p1, p2, p4, p6, p8) write a new image SHA to
`values.yaml` and push it back to `main` so ArgoCD detects drift and syncs.

**The problem with `git pull --rebase && git push`:**
If two workflows run concurrently (e.g. a merge and a tag trigger firing at
the same time), both fetch the same HEAD, both commit locally, and the second
push fails with a non-fast-forward error. Because `&&` chains the commands,
the push failure propagates and the step exits non-zero — but the commit is
already local, not on `main`. ArgoCD never sees the tag update.

**The correct pattern (used in all CI workflows):**
```bash
git pull --rebase
git push || (git pull --rebase && git push)
```

Split `pull` and `push` so each has a distinct exit code. Retry the push
once on failure — the retry re-pulls the now-updated remote and pushes
cleanly. Two concurrent pushes resolve in at most two attempts.

**Why not `--force`?**
Force-pushing `main` would discard any commits that landed between the
workflow's checkout and its push. The retry-with-rebase approach is safe
because it incorporates those commits rather than overwriting them.

---

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

---

## Git push rejected when CI also writes to main

**Symptom:** Local push fails with:
```
! [rejected] main -> main (fetch first)
Updates were rejected because the remote contains work you do not have locally.
```

**Root cause:** CI pipelines write back to `main` after every build — they update `values.yaml` with the new image SHA. If you push while a CI run is in flight or just finished, your local branch is behind.

**Fix:** Always `git pull --rebase` before pushing:
```bash
git add <files>
git commit -m "..."
git pull --rebase
git push
```

If there are unstaged changes that block the rebase:
```bash
git add <unstaged files>
git commit -m "..."   # or: git stash + pull --rebase + stash pop
git push
```

**Prevention:** Run `git pull --rebase` before starting any commit, not just before pushing.

---

## Git push stuck — SSH multiplexing socket

**Symptom:** `git push` or `git pull` hangs indefinitely with no output. Sometimes preceded by:
```
mux_client_request_session: read from master failed: Broken pipe
ControlSocket ~/.ssh/socket-git@github.com-22 already exists, disabling multiplexing
```

**Root cause:** SSH multiplexing reuses an existing SSH connection for speed. When the master connection dies (network drop, session timeout, SSH agent restart), the socket file remains on disk. Subsequent git commands try to reuse the dead socket, hang waiting for a response that never comes.

**Fix:**
```bash
rm -f ~/.ssh/socket-git@github.com-22
git push   # or git pull
```

**If the socket doesn't exist but it's still stuck:** the remote rejected the push because CI pushed first. Pull first then push:
```bash
git pull --rebase && git push
```

**Prevention:** Both issues stem from the same root: always do `git pull --rebase` before pushing, and if a push hangs, kill it (`Ctrl+C`), remove the socket, and retry.
