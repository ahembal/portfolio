# GitOps Image Updates
*How new container images reach production — current approach, limitations, and alternatives.*

---

## The problem

When CI builds a new image and pushes it to GHCR, Kubernetes doesn't automatically
use it. The image tag in `values.yaml` must be updated for ArgoCD to detect a change
and roll out the new pod.

---

## Current approach — CI writes the tag

After a successful build, each CI pipeline:

```
1. Build image → push to GHCR with full SHA tag
        │
        ▼
2. Check out repo
        │
        ▼
3. sed: replace tag in values.yaml with new SHA
        │
        ▼
4. git commit "ci(p1): update image tag to <sha>"
        │
        ▼
5. git pull --rebase && git push
        │
        ▼
6. ArgoCD detects values.yaml change → rolls out new pod
```

This is implemented in `.github/workflows/ci.yml` for each project.

### Limitation — race condition

If two commits are pushed in quick succession, two CI runs start simultaneously.
Both build images and both try to update `values.yaml`. The second push fails
because `main` moved forward:

```
Run A: push tag A → values.yaml → commit → push ✓
Run B: push tag B → values.yaml → commit → push ✗ (rejected, A moved main)
       git pull --rebase → push ✓ (sometimes)
                        → fails silently (occasionally)
```

When it fails, `values.yaml` keeps the old tag. ArgoCD does not roll out the
new image. The fix is to push again manually or retrigger CI.

In practice for this portfolio this is rare — it requires two near-simultaneous
pushes. The `git pull --rebase && git push` in CI handles most cases.

---

## Alternative — ArgoCD Image Updater

ArgoCD Image Updater is a controller that watches a container registry for new
image tags and updates `values.yaml` automatically — without CI involvement.
This eliminates the race condition because there is only one writer.

### How it would work

```
CI builds image → pushes to GHCR
        │
        ▼
Image Updater polls GHCR every 2 minutes
  Detects new tag for ghcr.io/ahembal/pcam-inference
        │
        ▼
Image Updater updates values.yaml via git (SSH deploy key)
  commits "ci(p1): update image tag to <sha>"
        │
        ▼
ArgoCD detects change → rolls out new pod
```

CI no longer writes to git at all — it just builds and pushes the image.

### Current status — not working

ArgoCD Image Updater v1.1.1 is installed but cannot list tags from GHCR.
The error: `denied: denied` from `https://ghcr.io/v2/ahembal/pcam-inference/tags/list`.

Root cause: GHCR requires OAuth Bearer token authentication for the v2 API.
Image Updater v1.1.1 sends Basic auth, which GHCR rejects. This is a known
compatibility issue between ArgoCD Image Updater and GHCR's authentication flow.

The Image Updater CR and Helm install remain in place for when this is resolved
(either by upgrading Image Updater or configuring a different credential format).

### Resources installed for Image Updater

| Resource | Namespace | Purpose |
|----------|-----------|---------|
| `argocd-image-updater` Helm release | argocd | Controller deployment |
| `argocd-image-updater-ssh-key` secret | argocd | SSH deploy key for git write-back |
| `argocd-image-updater-ghcr` secret | argocd | GHCR credentials (currently failing) |
| `pcam-inference` ImageUpdater CR | argocd | Watches pcam image, writes to values.yaml |
| Deploy key `argocd-image-updater` | GitHub | Write access to portfolio repo |

---

## Recommendation

Keep the CI-based approach for now. The race condition is rare and the manual
workaround (retrigger CI) is acceptable for a homelab portfolio.

Revisit Image Updater when v1.2+ is released or when a working GHCR credential
format is documented by the Image Updater maintainers.
