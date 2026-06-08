# ACMG-Lingua Production Deployment (Ansible)

Production environment provisioning and deployment via Ansible.

## Prerequisites

- Ansible >= 2.14 on the control machine
- Target hosts: Ubuntu 22.04+ / Debian 12+ with SSH access
- `deploy` user with sudo privileges on all hosts
- `community.docker` collection (`ansible-galaxy collection install community.docker`)

## Directory Structure

```
deploy/ansible/
├── ansible.cfg                              # Ansible configuration
├── .vault_pass                              # Vault password file (git-ignored)
├── .gitignore
├── inventories/
│   └── production/
│       ├── hosts.yml                        # Multi-server inventory
│       ├── hosts-single-server.yml.example  # Single-server inventory template
│       └── group_vars/
│           ├── all.yml                      # Structural config (safe to commit)
│           ├── vault.yml.example            # Secrets template
│           └── vault.yml                    # Encrypted secrets (git-ignored)
├── playbooks/
│   ├── site.yml                             # Main deployment playbook
│   └── healthcheck.yml                      # Post-deployment verification
├── roles/
│   ├── common/                              # Base packages, sysctl, logrotate, deploy user
│   ├── postgres/                            # PostgreSQL 16 (Docker) + daily backup
│   ├── redis/                               # Redis 8.0 (Docker)
│   ├── backend/                             # FastAPI backend (uv + systemd)
│   ├── model-server/                        # Embedding/Rerank/LLM server (systemd)
│   ├── frontend/                            # Next.js frontend (nvm + systemd)
│   └── nginx/                               # Nginx reverse proxy + auto TLS via certbot
└── templates/                               # Shared templates (if needed)
```

## Quick Start

### 1. Configure Inventory

Edit `inventories/production/hosts.yml` and replace placeholder IPs:

```yaml
web-01:
  ansible_host: "203.0.113.10"   # Your web server IP
app-01:
  ansible_host: "203.0.113.20"   # Your app server IP
db-01:
  ansible_host: "203.0.113.30"   # Your database server IP
```

For single-server deployment, use the provided example:

```bash
cp inventories/production/hosts-single-server.yml.example \
   inventories/production/hosts.yml
# Then edit YOUR_SERVER_IP
```

### 2. Configure Secrets

```bash
# Copy the example vault
cp inventories/production/group_vars/vault.yml.example \
   inventories/production/group_vars/vault.yml

# Edit with your real secrets
ansible-vault encrypt inventories/production/group_vars/vault.yml

# Set vault password
echo "your-vault-password" > .vault_pass
chmod 600 .vault_pass
```

### 3. Configure Domain

Edit `inventories/production/group_vars/all.yml`:

```yaml
domain_name: "acmg-lingua.your-domain.com"
tls_email: "[redacted-email]"
acmg_cors_origins: "https://acmg-lingua.your-domain.com"
```

### 4. Deploy

```bash
cd deploy/ansible

# Install required collections
ansible-galaxy collection install community.docker

# Full deployment (all services)
ansible-playbook playbooks/site.yml

# Deploy specific components
ansible-playbook playbooks/site.yml --tags infra       # DB + Redis + Model Server
ansible-playbook playbooks/site.yml --tags backend      # Backend only
ansible-playbook playbooks/site.yml --tags frontend     # Frontend + Nginx

# Dry run (check mode)
ansible-playbook playbooks/site.yml --check --diff

# Post-deployment health check
ansible-playbook playbooks/healthcheck.yml
```

## Host Topology

| Group   | Host     | Services                        | Port         |
|---------|----------|---------------------------------|--------------|
| `web`   | web-01   | Nginx, Frontend (Next.js)       | 80/443, 3000 |
| `app`   | app-01   | Backend (FastAPI), Model Server | 8000, 8001   |
| `db`    | db-01    | PostgreSQL 16, Redis 8.0        | 5432, 6379   |

## Architecture

```
Client (HTTPS)
    │
    ▼
┌───────────────────────┐
│   Nginx (web-01)      │  TLS termination, reverse proxy, certbot
│   :80 → :443          │
└───┬───────────┬───────┘
    │           │
    ▼           ▼
┌────────┐  ┌────────────┐
│Frontend│  │  Backend   │
│ :3000  │  │  :8000     │
└────────┘  └──┬─────┬──┘
               │     │
               ▼     ▼
         ┌────────┐ ┌──────────────┐
         │Redis   │ │ Model Server │
         │:6379   │ │ :8001 (GPU)  │
         └────────┘ └──────────────┘
               │
               ▼
         ┌────────────┐
         │ PostgreSQL │
         │ :5432      │
         │ + backup   │
         └────────────┘
```

## TLS / Let's Encrypt

TLS certificates are **automatically provisioned** by the nginx role via certbot:

1. First deploy starts Nginx in HTTP-only mode
2. Certbot obtains the certificate using `--nginx` authenticator
3. Nginx site config is automatically redeployed with TLS
4. Auto-renewal via `certbot.timer` systemd unit

No manual certbot steps needed. Just ensure DNS A record points to the web server before deploying.

## Automated Backup

PostgreSQL daily backup runs at 03:00 via cron:

- Backup path: `/opt/acmg-lingua-data/postgres-backups/`
- Format: `acmg_lingua_YYYYMMDD_HHMMSS.sql.gz`
- Retention: 30 days (auto-pruned)
- Manual restore: `gunzip < backup.sql.gz | docker exec -i acmg-postgres psql -U acmg_app -d acmg_lingua`

## Maintenance

```bash
# Check service status
ansible app -m systemd -a "name=acmg-backend" --become
ansible web -m systemd -a "name=acmg-frontend" --become

# View logs
ansible app -m shell -a "journalctl -u acmg-backend -n 50 --no-pager" --become

# Run health check
ansible-playbook playbooks/healthcheck.yml

# Rolling restart (backend only)
ansible-playbook playbooks/site.yml --tags backend
```

## Security Notes

- `vault.yml` is **git-ignored** and encrypted with `ansible-vault`
- `.vault_pass` is **git-ignored** — never commit it
- All systemd services run with `NoNewPrivileges` and `ProtectSystem=strict`
- Nginx enforces TLS 1.2+, security headers, and gzip
- Database ports are not exposed to the public internet (bind to private network)
- Log rotation: 30 days, auto-compressed
- TLS auto-renewal via certbot timer
