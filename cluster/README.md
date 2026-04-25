# cluster/ — Ansible Cluster Management

Ansible playbooks and roles for the homelab Kubernetes cluster.

## Cluster overview

| Node | Role | IP | OS | Kernel |
|------|------|----|----|--------|
| clever-fly | control-plane (cordoned) | 192.168.1.184 | Ubuntu 24.04.3 | 6.8.0-106 |
| quick-thrush | worker (stable) | 192.168.1.200 | Ubuntu 24.04.3 | 6.8.0-106 |
| sought-perch | worker (Flannel issue) | 192.168.1.16 | Ubuntu 24.04.3 | 6.8.0-110 |

**Note on sought-perch:** Had a Flannel VXLAN bug (kernel 6.8.0-101) causing CNI sandbox
rebuilds every ~7 minutes — all pods on the node received SIGTERM. Upgraded to 6.8.0-110
but liveness probe failures persist on the node — HTTP probes from pods on sought-perch
fail intermittently, causing Kubernetes to restart healthy pods (exit code 0). Root cause
not yet confirmed (Flannel VXLAN residual, NIC driver, or MTU mismatch).

**Workaround in place:** ArgoCD, CoreDNS, Sealed Secrets controller, and kube-prometheus
are all pinned to quick-thrush via nodeSelector. New workloads should also avoid
sought-perch until this is resolved.

**TODO — fix sought-perch properly:**
1. Check Flannel MTU: `kubectl exec -n kube-flannel <flannel-pod-on-sought-perch> -- cat /run/flannel/subnet.env`
2. Compare NIC MTU: `ip link show` on sought-perch vs quick-thrush
3. Check for dropped packets: `netstat -s | grep retransmit` on sought-perch
4. If MTU mismatch: patch Flannel configmap with explicit `"Backend": {"Type": "vxlan", "MTU": 1450}`
5. If NIC issue: check `dmesg | grep -i eth` for driver errors
6. After fix: remove nodeSelector pins from all affected deployments

## Installed stack

| Component | Version | Namespace |
|-----------|---------|-----------|
| Kubernetes | v1.29.15 | — |
| containerd | 1.7.28 | — |
| Flannel | v0.25.6 | kube-flannel |
| ArgoCD | v3.3.6 | argocd |
| Sealed Secrets | 0.27.3 | kube-system |
| kube-prometheus-stack | 83.6.0 | monitoring |
| ceph-csi-rbd | 3.16.1 | ceph-csi-rbd |

## Directory structure

```
cluster/
├── ansible.cfg                    # default inventory, SSH settings
├── inventory/
│   ├── hosts.ini                  # nodes + groups
│   └── group_vars/
│       ├── all.yml                # shared vars (versions, CIDRs, DNS)
│       ├── control_plane.yml      # control-plane vars
│       └── workers.yml            # worker vars
├── playbooks/
│   ├── bootstrap.yml              # full cluster: OS → containerd → kubeadm init → Flannel
│   ├── join-node.yml              # add a new worker node
│   ├── upgrade.yml                # rolling kubeadm upgrade
│   ├── configure-dns.yml          # systemd-resolved drop-in (MAAS DNS)
│   ├── install-argocd.yml         # ArgoCD + nodeSelector pins
│   ├── install-sealed-secrets.yml # Sealed Secrets controller + key backup
│   └── install-monitoring.yml     # kube-prometheus-stack + pcam ServiceMonitor
└── roles/
    ├── common/        # apt packages, swap off, sysctl, kernel modules
    ├── containerd/    # container runtime, SystemdCgroup=true
    ├── kubeadm/       # kubeadm/kubelet/kubectl install + pin
    ├── dns/           # systemd-resolved drop-in for MAAS DNS
    ├── argocd/        # (stub — logic in install-argocd.yml)
    ├── sealed-secrets/
    └── monitoring/
```

## Common operations

### Run a playbook
```bash
# Full bootstrap (fresh nodes from MAAS)
ansible-playbook playbooks/bootstrap.yml

# Fix DNS on all nodes (idempotent)
ansible-playbook playbooks/configure-dns.yml

# Add a new worker (add to inventory first)
ansible-playbook playbooks/join-node.yml --limit new-node-name

# Upgrade K8s (edit group_vars/all.yml k8s_version first)
ansible-playbook playbooks/upgrade.yml
```

### Check connectivity
```bash
ansible all -m ping
ansible all -m command -a "kubectl version --client" --limit control_plane
```

### Dry run
```bash
ansible-playbook playbooks/upgrade.yml --check --diff
```

## Design decisions

**Why Ansible over Terraform here?**
MAAS handles bare-metal provisioning. Terraform/Pulumi shine at infra provisioning;
Ansible fills the gap for node configuration (OS packages, sysctl, CNI) and cluster
bootstrap (kubeadm, ArgoCD, Sealed Secrets) — the "day 0/1" operations that ArgoCD
cannot bootstrap itself.

**Why not Kubespray?**
Kubespray is Ansible under the hood but adds ~200 variables and significant complexity
for a 3-node homelab. These playbooks are explicit and minimal — every task corresponds
to a step taken during manual cluster setup.

**Compliance references:**
- CIS Kubernetes Benchmark v1.9 — kubeadm defaults, RBAC, securityContext
- NIST SP 800-190 — container runtime hardening (containerd, non-root)
- ISO 27001:2022 A.12.6 — vulnerability management (package pinning, hold)
