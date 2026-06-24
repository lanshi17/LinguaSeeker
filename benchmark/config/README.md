# benchmark/config -- Centralized Configuration for the Benchmark Suite

Single home for benchmark configuration. Two complementary mechanisms:
**Ansible** renders tunable/secret config files into their consumer locations,
and **`defaults.py`** is the canonical source for runtime code constants
previously duplicated across runners.

## Quick Start

```bash
# 1. Install ansible-core
uv tool install ansible-core

# 2. Bootstrap secrets + vault password (first checkout only)
cd benchmark/config
openssl rand -base64 48 > .vault_pass && chmod 600 .vault_pass
cp vault/secrets.example.yml vault/secrets.yml
#   ...edit vault/secrets.yml with real values...
ansible-vault encrypt vault/secrets.yml

# 3. Render all managed config files into their consumer locations
ansible-playbook playbooks/deploy-config.yml
# -> benchmark/datasets/rett_annotation/{config.yaml, .env}
# -> benchmark/data/inputs/literature_acquisition/{rett_config.json, rett_config_02.json}
```

Re-running the playbook reports `changed=0` when nothing changed -- it is idempotent.

Runtime constants need no rendering -- just import them:

```python
from benchmark.config.defaults import DEFAULT_PIPELINE_BASE_URL, RETT_CONFIG_PATH
```

## Layout

```
benchmark/config/
├── __init__.py                       # Package marker + scope docstring
├── defaults.py                       # Runtime code constants (single source)
├── ansible.cfg                       # Inventory, roles_path, vault pass
├── inventories/local/
│   ├── hosts.yml                     # localhost in the `benchmark` group
│   └── group_vars/benchmark.yml      # Non-secret vars for rendered file configs
├── playbooks/deploy-config.yml       # Renders all file configs
├── roles/
│   ├── rett_annotation_config/       # Renders config.yaml + .env (secrets via vault)
│   │   ├── tasks/main.yml
│   │   └── templates/{config.yaml.j2, .env.j2}
│   └── rett_acquisition_config/      # Deploys static rett_config*.json (copy, not template)
│       ├── tasks/main.yml
│       └── files/literature_acquisition/{rett_config.json, rett_config_02.json}
└── vault/
    ├── secrets.example.yml           # Placeholder (committed)
    └── secrets.yml                   # Real secrets, ansible-vault encrypted (gitignored)
```

## Architecture

### Flow 1: Ansible-rendered file configs

```
group_vars/benchmark.yml (non-secret)   vault/secrets.yml (encrypted)
        rett_annotation_*                       rett_annotation_secrets
                |                                      |
        +-------+--------+                         (only for .env)
        | deploy-config.yml |
        |  roles:           |
        |   rett_annotation_config   -> template -> config.yaml (0644) + .env (0600)
        |   rett_acquisition_config  -> copy     -> rett_config.json + rett_config_02.json
        +-----------+-------+
                    v
   benchmark/datasets/rett_annotation/         <- read by src/config.py
   benchmark/data/inputs/literature_acquisition/  <- read by runners/literature_rett.py
```

### Flow 2: Runtime code constants (`defaults.py`)

```python
from benchmark.config.defaults import (
    DEFAULT_PIPELINE_BASE_URL,   # "http://localhost:8000"
    PHASE2_TERMINAL_STATUSES,    # {"completed", "failed", "skipped"}
    FILTER_TIER1_KEEP_THRESHOLD, # 3
    DEFAULT_SEED_QUERIES,        # 25 Rett/MECP2 queries
    RETT_CONFIG_PATH,            # data/inputs/literature_acquisition/rett_config.json
)
```

Constants are imported by runners (`phase2_batch`, `benchmark_b_phase2_sample`, `filter_variant_evidence`, `literature_rett`). Paths resolve from `BENCHMARK_ROOT` so they are correct regardless of runner CWD.

## What is Managed

### File configs (Ansible-rendered)

| Rendered file | Mechanism | Consumer |
| --- | --- | --- |
| `benchmark/datasets/rett_annotation/config.yaml` | template (0644) | `rett_annotation/src/config.py` |
| `benchmark/datasets/rett_annotation/.env` | template (0600, no_log) | `rett_annotation/src/config.py` |
| `benchmark/data/inputs/literature_acquisition/rett_config.json` | copy (0644) | `runners/literature_rett.py` |
| `benchmark/data/inputs/literature_acquisition/rett_config_02.json` | copy (0644) | `runners/literature_rett.py` |

### Runtime constants (`defaults.py`)

| Constant | Value | Description |
| --- | --- | --- |
| `DEFAULT_PIPELINE_BASE_URL` | `http://localhost:8000` | Backend API endpoint |
| `PHASE2_ARTIFACT_RELATIVE_PATH` | `phase_2/extraction_result.json` | Phase 2 result location |
| `PHASE2_TERMINAL_STATUSES` | `{completed, failed, skipped}` | Terminal statuses |
| `PIPELINE_FAILURE_STATUSES` | `{failed}` | Failure-only subset |
| `FILTER_TIER1_KEEP_THRESHOLD` | `3` | Variant filter keep threshold |
| `FILTER_TIER1_REJECT_THRESHOLD` | `0` | Variant filter reject threshold |
| `DEFAULT_SEED_QUERIES` | 25 Rett/MECP2 queries | Seed query list for literature_rett |
| `RETT_CONFIG_PATH` / `RETT_CONFIG_02_PATH` | `data/inputs/literature_acquisition/rett_config*.json` | Canonical config paths |

### Deliberately NOT moved here

| Item | Home | Reason |
| --- | --- | --- |
| `POLL_INTERVAL_S` / `MAX_POLL_ATTEMPTS` / `TERMINAL_STATUSES` | `benchmark/core/pipeline_client.py` | Bound to `submit_and_poll` + test monkeypatch contract |
| `BENCHMARK_ROOT` / `GROUND_TRUTH_ROOT` / `REPORTS_ROOT` | `benchmark/core/paths.py` | Already centralized |
| `benchmark/data/inputs/pipeline/manifest.json` | `data/inputs/pipeline/` | Input data manifest, not tunable config |
| `benchmark/datasets/rett_annotation/ground_truth/manifest.json` | `rett_annotation/ground_truth/` | Ground-truth data (800+ entries), not config |

## Usage Patterns

### Change the LLM model / endpoint (rett_annotation)

```bash
# edit inventories/local/group_vars/benchmark.yml: rett_annotation_llm.model
ansible-playbook playbooks/deploy-config.yml
```

### Edit the multilingual acquisition config

```bash
# edit benchmark/config/roles/rett_acquisition_config/files/literature_acquisition/rett_config.json
ansible-playbook playbooks/deploy-config.yml
```

### Tune a filter threshold or pipeline base URL

Edit `benchmark/config/defaults.py` directly -- no playbook needed. Runners pick it up on next import.

### Rotate a secret

```bash
ansible-vault edit vault/secrets.yml
ansible-playbook playbooks/deploy-config.yml
```

### Verify a fresh checkout

```bash
ansible-playbook playbooks/deploy-config.yml          # changed=4
ansible-playbook playbooks/deploy-config.yml | tail -1 # changed=0 (idempotent)
```

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| ansible-core | 2.19.11 | Playbook engine, `template`/`copy`/`file`, `ansible-vault` |
| Jinja2 | (bundled) | Template rendering |
| PyYAML | (bundled) | YAML vars + vault parsing |
| benchmark.core.paths | (internal) | `BENCHMARK_ROOT` for path resolution |

Install via `uv tool install ansible-core`.

## Testing

```bash
# 1. Playbook syntax
ansible-playbook playbooks/deploy-config.yml --syntax-check

# 2. Render + idempotency
ansible-playbook playbooks/deploy-config.yml
ansible-playbook playbooks/deploy-config.yml | tail -1   # changed=0

# 3. Full benchmark test suite
cd backend && uv run pytest tests/benchmark/ -q
```
