# Operations Log

Live cluster changes that don't appear in code — manual fixes, node operations,
config changes applied directly to the cluster. Each entry records what was done,
why, and the current state so the cluster can be reconstructed after a failure.

---

## 2026-04-27 — NTP clock skew fix (ISS-001)

**Problem:** All 3 nodes were pointing NTP at `192.168.1.87` (old MAAS IP).
MAAS had moved to `192.168.1.90`. Clocks drifted ~137 seconds. Ceph monitors
rejected OSDs, 100% of PGs became inactive, all PVC I/O blocked.

**Changes made:**
- `/etc/systemd/timesyncd.conf.d/cloud-init.conf` updated on all 3 nodes:
  `NTP=192.168.1.87` → `NTP=192.168.1.90`
- Clocks force-stepped to correct UTC: `timedatectl set-ntp false && sudo date -u -s "..."`
- Ceph monitors restarted: `ceph orch daemon restart mon.quick-thrush mon.sought-perch`
- Ceph OSDs restarted: `ceph orch daemon restart osd.2 osd.3`

**Current state:** All 3 monitors healthy, 4/6 OSDs up. osd.0 and osd.1 on
sought-perch remain at reweight=0 intentionally (node instability at the time).

**Permanent fix:** `cluster/playbooks/configure-ntp.yml` — run after any MAAS IP change.

---

## 2026-04-27 — Ceph StorageClass created (ISS-004, ISS-006)

**Problem:** No default StorageClass existed. Ceph CSI installed but StorageClass
never created. PVCs pending indefinitely. StorageClass initially created with
wrong pool name `kubernetes` — actual pool is `k8s-rbd`.

**Changes made:**
```bash
kubectl apply -f cluster/manifests/ceph-rbd-storageclass.yaml
```
StorageClass `ceph-rbd` created with `pool: k8s-rbd`, set as cluster default.

**Current state:** PVCs provision successfully via Ceph RBD.

---

## 2026-04-27 — sealed-secrets controller pinned to quick-thrush

**Problem:** sealed-secrets controller on sought-perch was crash-looping due to
liveness probe failures. Controller must be stable to unseal secrets at pod startup.

**Change made:**
```bash
kubectl patch deployment sealed-secrets-controller -n kube-system \
  --type=json -p='[{"op":"add","path":"/spec/template/spec/nodeSelector",
  "value":{"kubernetes.io/hostname":"quick-thrush"}}]'
```

**Permanent fix:** `cluster/playbooks/install-sealed-secrets.yml` updated with
`--set nodeSelector."kubernetes\.io/hostname"=quick-thrush`.

---

## 2026-04-28 — sought-perch node drain and rejoin (ISS-002)

**Problem:** kube-proxy on sought-perch crash-looping for 7+ days (14,398
restarts, exit code 2). Root cause: corrupt iptables KUBE-* chains from 14,000+
partial writes during crash loops. All pods on node had failing liveness probes.

**Steps executed:**
```bash
# 1. Drain all workloads off the node
kubectl drain sought-perch --ignore-daemonsets --delete-emptydir-data --force

# 2. Remove from cluster
kubectl delete node sought-perch

# 3. On sought-perch — wipe all Kubernetes state
sudo kubeadm reset --force
sudo rm -rf /etc/cni/net.d/*
sudo iptables -F && sudo iptables -X
sudo iptables -t nat -F && sudo iptables -t nat -X
sudo ip link delete flannel.1
sudo ip link delete cni0
sudo rm -rf /var/lib/cni/
sudo systemctl restart kubelet

# 4. Generate fresh join token from control plane
ssh clever-fly "sudo kubeadm token create --print-join-command"

# 5. Rejoin
sudo kubeadm join 192.168.1.184:6443 \
  --token <token> \
  --discovery-token-ca-cert-hash sha256:<hash>
```

**Current state:** sought-perch Ready, kube-proxy 0 restarts, Flannel clean.
Full 2-node worker capacity restored.

---

## 2026-04-28 — ghcr-pull-secret refreshed in all namespaces

**Problem:** ghcr-pull-secret in cluster namespaces contained an expired PAT.
GHCR returns 404 Not Found (not 401) for expired credentials on private images —
misleading error that looks like a missing image.

**Changes made:**
```bash
# Token: $GHCR_TOKEN from ~/.bashrc
# Also stored in pass: homelab/github/ghcr-pull-token
for ns in metadata pcam; do
  kubectl create secret docker-registry ghcr-pull-secret \
    --docker-server=ghcr.io \
    --docker-username=ahembal \
    --docker-password=$GHCR_TOKEN \
    --namespace $ns \
    --dry-run=client -o yaml | kubectl apply -f -
done
```

**TODO:** Auto-rotate via GitHub App + CronJob. PAT will expire again.

---

## 2026-04-28 — ssh-quick-thrush-tailscale alias added to ~/.bashrc

**Problem:** No Tailscale alias for quick-thrush. Outside the home network the
local IP `192.168.1.200` is unreachable.

**Change made:**
```bash
echo "alias ssh-quick-thrush-tailscale='ssh -i ~/.ssh/turtle_key ubuntu@100.82.75.34'" >> ~/.bashrc
```

**All cluster node aliases:**

| Node | Role | Local IP | Tailscale IP | Alias |
|------|------|----------|--------------|-------|
| clever-fly | K8s control-plane | 192.168.1.184 | 100.123.23.6 | `ssh-clever-fly-tailscale` |
| quick-thrush | K8s worker | 192.168.1.200 | 100.82.75.34 | `ssh-quick-thrush-tailscale` |
| sought-perch | K8s worker | 192.168.1.16 | 100.69.132.9 | `ssh-sought-perch-tailscale` |
| alert-lizard | Ceph MON/OSD | 192.168.1.183 | 100.119.255.51 | `ssh-alert-lizard-tailscale` |
| MAAS controller | Infra | 192.168.1.90 | 100.124.69.85 | `ssh-turtle-mgmn-tailscale` |
