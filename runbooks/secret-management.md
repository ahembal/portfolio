# Secret Management

## Current approach: GPG + pass + SealedSecrets

### Overview

```
Secrets at rest (local machine)
  └── pass (~/.password-store, GPG-encrypted)
        │
        └── used to populate env vars at seal time
                      │
                      ▼
              kubeseal encrypts secrets
              with the cluster's public key
                      │
                      ▼
              SealedSecret YAML committed to git
              (encrypted — safe to store in repo)
                      │
                      ▼
              Sealed Secrets controller in cluster
              decrypts → creates Kubernetes Secret
                      │
                      ▼
              Pod reads secret from env var / volume
```

### Why this way?

- Plain text secrets must never be written to disk or committed to git
- `pass` encrypts everything with GPG — only the key holder can read them
- `SealedSecrets` lets us commit encrypted credentials to git safely —
  the Sealed Secrets controller is the only thing that can decrypt them
  (using the cluster's private key, which never leaves the cluster)

### GPG key

Created 2026-04-25, no passphrase (temporary — will be replaced when Vault is deployed):

```
Fingerprint: AD9834B76359AEBEB8BF24D6BE5494B1804D261C
Name:        Emre Balsever <a.emrebalsever@gmail.com>
Type:        RSA 4096
Expires:     never
```

> **Note:** No passphrase was set because this is a transitional setup.
> When HashiCorp Vault is deployed (see roadmap below), secrets will be
> pulled from Vault directly and `pass` will no longer be needed for
> cluster operations.

### Secret store layout

```
pass ls
└── homelab/
    ├── rgw/
    │   ├── access-key      Ceph RGW S3 access key (shared across projects)
    │   └── secret-key      Ceph RGW S3 secret key
    └── p2/
        └── postgres-password   PostgreSQL password for metadata-ingestion
```

### How to seal secrets for a project

```bash
# Retrieve secrets from pass and pipe into the seal script
RGW_ACCESS_KEY=$(pass homelab/rgw/access-key) \
RGW_SECRET_KEY=$(pass homelab/rgw/secret-key) \
POSTGRES_PASSWORD=$(pass homelab/p2/postgres-password) \
./k8s/seal-secrets.sh
```

The output files (`sealed-secret-*.yaml`) are encrypted and safe to commit.

### How to add a new secret

```bash
# Generate a random password
openssl rand -base64 24 | tr -d '=/+' | head -c 32 | pass insert -e homelab/<project>/<name>

# Or store a known value
echo "my-value" | pass insert -e homelab/<project>/<name>

# Retrieve it
pass homelab/<project>/<name>
```

---

## Roadmap: migrating to HashiCorp Vault

`pass` is a local tool — secrets live only on this machine. If the machine is
lost or you need to share access with another operator, there is no safe way to
do that with `pass` alone.

**HashiCorp Vault** is the proper long-term solution:

| Feature | pass (now) | Vault (planned) |
|---------|-----------|-----------------|
| Encryption | GPG | AES-256-GCM + TLS |
| Access control | filesystem permissions | Policies + AppRole / K8s auth |
| Audit log | none | full read/write audit trail |
| Dynamic secrets | no | yes (e.g. short-lived DB passwords) |
| Multi-user | no | yes |
| K8s integration | manual | Vault Agent auto-injects secrets into pods |

### Planned Vault deployment

- Run Vault as a StatefulSet on the homelab cluster (HA with Raft storage)
- K8s auth method: pods authenticate with their ServiceAccount token
- Vault Agent Injector: secrets injected as env vars at pod startup —
  no SealedSecrets needed, no secrets ever touch git
- Unseal: manual unseal keys stored in a safe place (or auto-unseal with a KMS)

**When to do this:** before adding more projects or more operators.
Tracked as a cluster improvement task — see `cluster/` for Ansible playbooks.

### Migration path

1. Deploy Vault on the cluster
2. Enable K8s auth method
3. Write policies for each namespace (metadata, pcam, etc.)
4. Move secrets from `pass` into Vault
5. Update Helm charts to use Vault Agent annotations instead of SealedSecrets
6. Remove `sealed-secrets-controller` from the cluster
