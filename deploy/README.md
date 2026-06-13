# deploy

> Deployment configuration for the CrossEvidence platform.

## Structure

```
deploy/
└── ansible/            # Ansible-based production deployment
    ├── roles/          # common, postgres, redis, backend, model-server, frontend, nginx
    ├── playbooks/      # site.yml, healthcheck.yml
    ├── inventories/    # production/
    └── templates/      # Shared templates
```

See [ansible/README.md](ansible/README.md) for full deployment documentation.

## Deployment Topology

```
Internet
    │
    ▼
┌─────────┐
│  Nginx   │  TLS termination, reverse proxy
│  :443    │
└────┬────┘
     │
     ├──→ Frontend (Next.js :3000)
     ├──→ Backend  (FastAPI :8000)
     │        │
     │        ├──→ PostgreSQL (:5432)
     │        ├──→ Redis (:6379)
     │        └──→ Model Server (:8001)
     │                └── GPU inference (Embedding, Rerank, VLM)
     └──→ Static assets
```

## Requirements

- Ubuntu 22.04+ target server(s)
- Ansible >= 2.14 with `community.docker` collection
- SSH access to target server(s)
- GPU server for model-server (NVIDIA driver + CUDA)

## Quick Deploy

```bash
cd deploy/ansible

# Full deployment
ansible-playbook playbooks/site.yml

# Health check only
ansible-playbook playbooks/healthcheck.yml
```
