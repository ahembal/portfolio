# Deployment Troubleshooting Log
*p1-pcam-deployment — Docker, Helm, CI, and serving issues*

See also:
- `k8s-issues.md` — Kubernetes cluster and infrastructure issues
- `model-issues.md` — model training, weights, and inference issues

---

## 1. Helm template parse error — `{{if}}` inside YAML comment

**Symptom:** `helm template` and `helm install` fail with:
```
Error: parse error at (pcam-inference/templates/hpa.yaml:47): unexpected EOF
```

**Root cause:** `hpa.yaml` had Go template syntax inside a YAML comment:
```yaml
# The `{{- if .Values.hpa.enabled }}` guard lets you disable HPA for
```
Go's `text/template` engine does not understand YAML comment syntax — `#` is just a
regular character. The `{{- if }}` inside the comment was parsed as a real template
action with no matching `{{- end }}`.

**Fix:** Remove `{{ }}` delimiters from comments in Helm templates.

**Lesson:** Never write Go template syntax inside YAML comments — the engine processes
them regardless of the `#` prefix.

---

## 2. Distroless image — CMD must use `-m uvicorn`, not bare `uvicorn`

**Symptom:**
```
/usr/bin/python3.11: can't open file '/app/uvicorn': [Errno 2] No such file or directory
```

**Root cause:** `gcr.io/distroless/python3-debian12:nonroot` sets
`ENTRYPOINT ["python3.11"]`. With `CMD ["uvicorn", ...]`, the full command becomes
`python3.11 uvicorn ...` — Python tries to open `uvicorn` as a script file.

**Fix:**
```dockerfile
CMD ["-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```

---

## 3. Distroless — PyTorch getpwuid() fails for non-existent UID

**Symptom:**
```
KeyError: 'getpwuid(): uid not found: 1000'
```

**Root cause:** PyTorch calls `pwd.getpwuid(os.getuid())`. The distroless `nonroot` image
only has UID 65532 in `/etc/passwd`. Deployment was setting `runAsUser: 1000`.

**Fix:**
1. Change `runAsUser` to `65532` (distroless nonroot UID)
2. Set `TORCHINDUCTOR_CACHE_DIR: "/tmp/torchinductor"` in the ConfigMap

---

## 4. Incorrect sys.path in container — parents[2] IndexError

**Symptom:**
```
IndexError: 2 (at Path(__file__).resolve().parents[2])
```

**Root cause:** In the repo `main.py` lives at `p1-pcam-deployment/serving/main.py` so
`parents[2]` reaches the repo root. In the container `main.py` is at `/app/main.py` so
`parents[2]` doesn't exist.

**Fix:**
```python
sys.path.insert(0, str(Path(__file__).resolve().parent / "infra" / "ceph-rgw"))
```

---

## 5. GitHub Actions — GHCR push 403

**Symptom:**
```
ERROR: failed to push ghcr.io/ahembal/pcam-inference:<sha>: 403 Forbidden
```

**Root cause (two-part):**

Part A — repo workflow permissions default to `read`. Fix:
```bash
gh api --method PUT repos/ahembal/portfolio/actions/permissions/workflow \
  --field default_workflow_permissions=write
```

Part B — new GHCR package not linked to repo. Fix: go to
`github.com/users/ahembal/packages/container/<name>/settings` → Manage Actions access →
add `portfolio` repo with Write access.

**Note:** Do this for every new image before the first CI push.

---

## 6. GitHub Actions — concurrent runs reject each other's tag-update push

**Symptom:**
```
! [rejected] main -> main (fetch first)
```

**Root cause:** Two CI runs triggered simultaneously both try to push the updated
`values.yaml` tag. The second is rejected because the first advanced the ref.

**Fix:**
```yaml
git pull --rebase && git push
```

---

## 7. CI — ruff fails on notebook E501 line-too-long

**Symptom:** `ruff check` fails on `train/kaggle_train.ipynb` with E501 errors.

**Fix:** Exclude notebooks in `pyproject.toml`:
```toml
[tool.ruff]
exclude = ["*.ipynb"]
```

---

## 8. CI — pytest cannot import `serving` or `boto3_config`

**Symptom:**
```
ModuleNotFoundError: No module named 'serving'
ModuleNotFoundError: No module named 'boto3_config'
```

**Root cause:** `pytest` runs from `p1-pcam-deployment/` without `serving/` or
`infra/ceph-rgw/` on `sys.path`.

**Fix:** Set `pythonpath` in `pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = [".", "serving", "../infra/ceph-rgw"]
```

---

## 9. CI — Prometheus metric re-registration error in pytest

**Symptom:**
```
ValueError: Duplicated timeseries in CollectorRegistry: {'pcam_requests_total', ...}
```

**Root cause:** `serving/main.py` registers Prometheus metrics at module level. pytest
imports the module once per test class, triggering re-registration on each import.

**Fix:** Wrapped metric registration in `try/except ValueError` — on re-import, retrieves
the already-registered collector from `REGISTRY`.

---

## 10. CI — timm not found when installing from PyTorch index

**Symptom:**
```
ERROR: Could not find a version that satisfies the requirement timm>=1.0.0
```

**Root cause:** Using `--index-url https://download.pytorch.org/whl/cpu` overrides the
default PyPI index. `timm` is only on PyPI, not the PyTorch index.

**Fix:** Use `--extra-index-url` instead — adds PyTorch as an extra source while keeping
PyPI as the default:
```yaml
pip install -r serving/requirements.txt --extra-index-url https://download.pytorch.org/whl/cpu
```
