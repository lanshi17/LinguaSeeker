# deploy/ansible/ -- Production Deployment

Ansible-based provisioning and deployment for LinguaSeeker production environments.

## Directory Structure

```
deploy/ansible/
├── ansible.cfg                              Ansible configuration
├── .vault_pass                              Vault password file (git-ignored)
├── .gitignore                               Ignores vault_pass, vault.yml
├── inventories/
│   └── production/
│       ├── hosts.yml                        Multi-server inventory
│       ├── hosts-single-server.yml.example  Single-server inventory template
│       ├── group_vars/
│       │   ├── all.yml                      Structural config (safe to commit)
│       │   └── vault.yml.example            Secrets template
├── playbooks/
│   ├── site.yml                             Main deployment playbook
│   └── healthcheck.yml                      Post-deployment verification
├── roles/
│   ├── common/                              Base packages, sysctl, logrotate, deploy user
│   ├── postgres/                            PostgreSQL 16 (Docker) + daily backup
│   ├── redis/                               Redis 8.0 (Docker)
│   ├── backend/                             FastAPI backend (uv + systemd)
│   ├── model-server/                        Embedding/Rerank/LLM server (systemd)
│   ├── frontend/                            Next.js frontend (bun + systemd)
│   └── nginx/                               Nginx reverse proxy + auto TLS via certbot
```

Each role follows standard Ansible structure: `tasks/`, `handlers/`, `defaults/`, `templates/`.

## Prerequisites

- Ansible >= 2.14 on the control machine
- Target hosts: Ubuntu 22.04+ / Debian 12+ with SSH access
- `deploy` user with sudo privileges on all hosts
- `community.docker` collection (`ansible-galaxy collection install community.docker`)

## Quick Start

### 1. Configure Inventory

Edit `inventories/production/hosts.yml` and replace placeholder IPs:

```yaml
web-01:
  ansible_host: "203.0.113.10"
app-01:
  ansible_host: "203.0.113.20"
db-01:
  ansible_host: "203.0.113.30"
```

For single-server deployment:

```bash
cp inventories/production/hosts-single-server.yml.example inventories/production/hosts.yml
```

### 2. Configure Secrets

```bash
cp inventories/production/group_vars/vault.yml.example inventories/production/group_vars/vault.yml
ansible-vault encrypt inventories/production/group_vars/vault.yml
echo "your-vault-password" > .vault_pass
chmod 600 .vault_pass
```

### 3. Deploy

```bash
cd deploy/ansible
ansible-galaxy collection install community.docker

# Full deployment
ansible-playbook playbooks/site.yml

# Deploy specific components
ansible-playbook playbooks/site.yml --tags infra       # DB + Redis + Model Server
ansible-playbook playbooks/site.yml --tags backend      # Backend only
ansible-playbook playbooks/site.yml --tags frontend     # Frontend + Nginx

# Dry run
ansible-playbook playbooks/site.yml --check --diff

# Post-deployment health check
ansible-playbook playbooks/healthcheck.yml
```

## Host Topology

| Group | Host | Services | Port |
|-------|------|----------|------|
| `web` | web-01 | Nginx, Frontend (Next.js via bun) | 80/443, 3000 |
| `app` | app-01 | Backend (FastAPI), Model Server | 8000, 8001 |
| `db` | db-01 | PostgreSQL 16, Redis 8.0 | 5432, 6379 |

## Architecture

```
Client (HTTPS)
    │
    ▼
┌───────────────────────┐
│   Nginx (web-01)      │  TLS termination, reverse proxy, certbot
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
         └────────────┘
```

## Key Features

- **TLS / Let's Encrypt** -- Automatically provisioned by the nginx role via certbot. First deploy starts HTTP-only, certbot obtains the cert, Nginx redeploys with TLS. Auto-renewal via `certbot.timer`.
- **Automated backup** -- PostgreSQL daily backup at 03:00 via cron. Stored at `/opt/lingua-seeker-data/postgres-backups/`, retained 30 days.
- **Security** -- `vault.yml` encrypted with `ansible-vault`, git-ignored. All systemd services run with `NoNewPrivileges` and `ProtectSystem=strict`. Database ports not exposed publicly.

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
