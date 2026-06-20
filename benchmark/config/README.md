# benchmark/config — centralized configuration for the benchmark suite

> The single home for benchmark configuration. Two complementary mechanisms:
> **Ansible** renders tunable/secret *config files* into their consumer locations,
> and **`defaults.py`** is the canonical source for *runtime code constants*
> previously duplicated across runners. Nothing benchmark-config-related is
> scattered elsewhere after this consolidation.

## Quick Start

```bash
# 1. Install ansible-core (project rule: modern tooling only)
uv tool install ansible-core

# 2. Bootstrap secrets + vault password (first checkout only)
cd benchmark/config
openssl rand -base64 24 > .vault_pass && chmod 600 .vault_pass
cp vault/secrets.example.yml vault/secrets.yml
#   …edit vault/secrets.yml with real values…
ansible-vault encrypt vault/secrets.yml

# 3. Render all managed config files into their consumer locations
ansible-playbook playbooks/deploy-config.yml
# → benchmark/datasets/rett_annotation/{config.yaml, .env}
# → benchmark/data/inputs/literature_acquisition/{rett_config.json, rett_config_02.json}
```

Re-running the playbook reports `changed=0` when nothing changed — it is idempotent.

Runtime constants need no rendering — just import them:

```python
from benchmark.config.defaults import DEFAULT_PIPELINE_BASE_URL, RETT_CONFIG_PATH
```

## Layout

```
benchmark/config/
├── __init__.py                       # package marker + scope docstring
├── defaults.py                       # ← runtime code constants (single source)
├── ansible.cfg                       # inventory, roles_path, vault pass
├── inventories/local/
│   ├── hosts.yml                     # localhost in the `benchmark` group
│   └── group_vars/benchmark.yml      # non-secret vars for rendered file configs
├── playbooks/deploy-config.yml       # renders all file configs
├── roles/
│   ├── rett_annotation_config/       # renders config.yaml + .env (secrets via vault)
│   │   ├── tasks/main.yml
│   │   └── templates/{config.yaml.j2, .env.j2}
│   └── rett_acquisition_config/      # deploys static rett_config*.json (copy, not template)
│       ├── tasks/main.yml
│       └── files/literature_acquisition/{rett_config.json, rett_config_02.json}
└── vault/
    ├── secrets.example.yml           # placeholder (committed)
    └── secrets.yml                   # real secrets, ansible-vault encrypted (gitignored)
```

## Architecture

Two independent flows share this home:

### Flow 1 — Ansible-rendered file configs

```
 group_vars/benchmark.yml (non-secret)   vault/secrets.yml (encrypted)
        rett_annotation_*                       rett_annotation_secrets
                │                                      │
        ┌───────┴────────┐                         (only for .env)
        │ deploy-config.yml │ vars_files: ../vault/secrets.yml
        │  roles:           │
        │   rett_annotation_config   → template → config.yaml (0644) + .env (0600, no_log)
        │   rett_acquisition_config  → copy     → rett_config.json + rett_config_02.json (0644)
        └───────────┬───────┘
                    ▼
   benchmark/datasets/rett_annotation/      ← read by src/config.py (Config loader)
   benchmark/data/inputs/literature_acquisition/  ← read by literature_rett.load_config()
```

`rett_acquisition_config` uses the `copy` module (not `template`) because the
rett_config JSON files are static content — per-language query arrays are
content, not variables. Templating 180+ lines of JSON into `group_vars` would
hurt readability for no benefit (rule 20.2: simple优先). `copy` is idempotent
via checksum.

### Flow 2 — Runtime code constants (`defaults.py`)

```
 benchmark/config/defaults.py  (canonical, hand-maintained)
   DEFAULT_PIPELINE_BASE_URL, PHASE2_* , FILTER_TIER1_*,
   DEFAULT_FILTER_*_DIRS, DEFAULT_SEED_QUERIES, RETT_CONFIG_PATH
        ▲
        │ import
   ┌────┴────────────────────────────────────────────┐
   │ benchmark/runners/phase2_batch.py               │
   │ benchmark/runners/benchmark_b_phase2_sample.py  │
   │ benchmark/runners/filter_variant_evidence.py    │
   │ benchmark/runners/literature_rett.py            │
   └─────────────────────────────────────────────────┘
```

Plus a **separate canonical source** kept on purpose: pipeline poll/retry
constants (`POLL_INTERVAL_S`, `MAX_POLL_ATTEMPTS`, `TERMINAL_STATUSES`) remain
in `benchmark/core/pipeline_client.py` because they are bound to the
`submit_and_poll` primitive and its test monkeypatch contract
(`benchmark.core.pipeline_client.POLL_INTERVAL_S` is monkeypatched in tests).
`pipeline_e2e.py` and `clingen_preprocess.py` previously *redefined* these
locally; they now import them from `benchmark.core`, removing the duplication
while preserving each runner's module-level name (so runner-level monkeypatch
surface is unchanged).

## What is managed

### File configs (Ansible-rendered)

| Rendered file | Mechanism | Source | Consumer |
| --- | --- | --- | --- |
| `benchmark/datasets/rett_annotation/config.yaml` | template (0644) | `group_vars` + `config.yaml.j2` | `rett_annotation/src/config.py` |
| `benchmark/datasets/rett_annotation/.env` | template (0600, no_log) | `vault/secrets.yml` + `.env.j2` | `rett_annotation/src/config.py` |
| `benchmark/data/inputs/literature_acquisition/rett_config.json` | copy (0644) | `roles/rett_acquisition_config/files/` | `runners/literature_rett.py load_config()` |
| `benchmark/data/inputs/literature_acquisition/rett_config_02.json` | copy (0644) | `roles/rett_acquisition_config/files/` | `runners/literature_rett.py --config` |

### Runtime constants (`defaults.py`)

| Constant | Value | Consumers (previously duplicated/scattered) |
| --- | --- | --- |
| `DEFAULT_PIPELINE_BASE_URL` | `http://localhost:8000` | `phase2_batch`, `benchmark_b_phase2_sample` (were 2 separate defs) |
| `PHASE2_ARTIFACT_RELATIVE_PATH` | `phase_2/extraction_result.json` | `phase2_batch`, `benchmark_b_phase2_sample` (duplicated) |
| `PHASE2_TERMINAL_STATUSES` | `{completed, failed, skipped}` | `phase2_batch`, `benchmark_b_phase2_sample` (duplicated) |
| `PIPELINE_FAILURE_STATUSES` | `{failed}` | `phase2_batch`, `benchmark_b_phase2_sample` (duplicated) |
| `FILTER_TIER1_KEEP_THRESHOLD` | `3` | `filter_variant_evidence` |
| `FILTER_TIER1_REJECT_THRESHOLD` | `0` | `filter_variant_evidence` |
| `DEFAULT_FILTER_INPUT_DIRS` | `[benchmark/literature_acquisition/downloads, benchmark/runners/downloads]` | `filter_variant_evidence` |
| `DEFAULT_FILTER_OUTPUT_DIR` | `benchmark/runners/downloads` | `filter_variant_evidence` |
| `DEFAULT_SEED_QUERIES` | 25 Rett/MECP2 queries | `literature_rett` (was 25-line inline list) |
| `RETT_CONFIG_PATH` / `RETT_CONFIG_02_PATH` | canonical rett_config paths | `literature_rett` (fixes stale default) |

### Deliberately NOT moved here

| Item | Home | Why |
| --- | --- | --- |
| `POLL_INTERVAL_S` / `MAX_POLL_ATTEMPTS` / `TERMINAL_STATUSES` | `benchmark/core/pipeline_client.py` | Bound to `submit_and_poll` + test monkeypatch contract. Runners now import from `benchmark.core` instead of redefining. |
| `BENCHMARK_ROOT` / `GROUND_TRUTH_ROOT` / `REPORTS_ROOT` / … | `benchmark/core/paths.py` | Already centralized; `defaults.py` imports `BENCHMARK_ROOT` from there. |
| `benchmark/data/inputs/pipeline/manifest.json` | `data/inputs/pipeline/` | Input data manifest (lists concrete PDFs + sizes), not tunable config. Per user decision. |
| `benchmark/datasets/rett_annotation/ground_truth/manifest.json` | `rett_annotation/ground_truth/` | Ground-truth data (800+ entries), not config. |
| `rett_annotation/pyproject.toml` | `rett_annotation/` | Tool project definition, not benchmark config. |
| `VARIANT_KEYWORDS` (filter) / `DEFAULT_SEED_QUERIES`-style content dicts in runners | in-place | Large content dictionaries tightly coupled to runner logic; not duplicated. |

## Internal Design

### File rendering is CWD-independent

`rett_annotation_dest_root` and `rett_acquisition_dest_dir` are both computed
from `playbook_dir` (absolute path of `benchmark/config/playbooks`):

```yaml
rett_annotation_dest_root: "{{ (playbook_dir | dirname | dirname) }}/datasets/rett_annotation"
rett_acquisition_dest_dir:  "{{ (playbook_dir | dirname | dirname) }}/data/inputs/literature_acquisition"
```

`playbook_dir | dirname | dirname` → `benchmark/`, so targets always resolve to
`<repo>/benchmark/...` regardless of where `ansible-playbook` is invoked.

### Inventory ↔ group_vars binding

`group_vars/benchmark.yml` loads only because `inventories/local/hosts.yml`
places `localhost` inside the `benchmark` group. Rename either side and the
vars silently go undefined. Verify with `ansible-inventory --list`.

### Idempotency

`template` (checksum of rendered content) and `copy` (checksum of file content)
both report `changed=0` on a no-op re-run. **Do not add `changed_when: true`**
to these tasks — it forces `changed=1` every run and defeats the point.

### `defaults.py` paths resolve from `BENCHMARK_ROOT`

```python
from benchmark.core.paths import BENCHMARK_ROOT
DEFAULT_FILTER_OUTPUT_DIR: Path = BENCHMARK_ROOT / "runners" / "downloads"
RETT_CONFIG_PATH: Path = BENCHMARK_ROOT / "data" / "inputs" / "literature_acquisition" / "rett_config.json"
```

`BENCHMARK_ROOT` is `benchmark/core/paths.py`'s `Path(__file__).resolve().parent.parent`
→ `<repo>/benchmark`, so the paths are correct regardless of runner CWD. This
fixes `literature_rett.py`'s stale `CONFIG_FILE = MODULE_DIR / "rett_config.json"`
default (MODULE_DIR was `benchmark/runners/`, where the file never lived).

### Import-swap preserves monkeypatch surface

Runners import constants as module-level names (e.g.
`from benchmark.core import POLL_INTERVAL_S`). The name is bound in the
runner's own namespace, so `benchmark.runners.pipeline_e2e.POLL_INTERVAL_S`
still resolves and is still monkeypatchable — identical to the prior local-def
behavior. Values are unchanged.

## Usage Patterns

### Change the LLM model / endpoint (rett_annotation)

```bash
# edit inventories/local/group_vars/benchmark.yml: rett_annotation_llm.model
$ ansible-playbook playbooks/deploy-config.yml
```

### Edit the multilingual acquisition config (rett_config)

```bash
# edit benchmark/config/roles/rett_acquisition_config/files/literature_acquisition/rett_config.json
$ ansible-playbook playbooks/deploy-config.yml
# → re-deploys to benchmark/data/inputs/literature_acquisition/
```

### Tune a filter threshold or pipeline base URL

Edit `benchmark/config/defaults.py` directly — no playbook needed:

```python
# benchmark/config/defaults.py
FILTER_TIER1_KEEP_THRESHOLD: int = 5   # was 3
```

Runners pick it up on next import. Re-run the relevant test to confirm.

### Rotate a secret

```bash
$ ansible-vault edit vault/secrets.yml
$ ansible-playbook playbooks/deploy-config.yml
```

### Verify a fresh checkout reproduces all configs

```bash
$ ansible-playbook playbooks/deploy-config.yml          # changed=4
$ ansible-playbook playbooks/deploy-config.yml | tail -1 # changed=0 (idempotent)
```

## Extension Guide

### Add a new Ansible-managed config file

1. If static content → put it under `roles/<new>/files/...` and use `copy`.
   If templated with vars → put a `.j2` under `roles/<new>/templates/` and add
   vars to `group_vars/benchmark.yml` (secrets → `vault/secrets.yml`).
2. Write `roles/<new>/tasks/main.yml` (mirror an existing role; `no_log: true`
   on any secret-bearing task).
3. Add a `rett_*_dest_*` path var to `group_vars/benchmark.yml` (resolve via
   `playbook_dir`).
4. Add the role under `roles:` in `playbooks/deploy-config.yml`.
5. Re-render and confirm idempotency.

### Add a new runtime constant

1. Add it to `benchmark/config/defaults.py` with a typed declaration + section
   comment + `__all__` entry.
2. In the runner, `from benchmark.config.defaults import X` (use `as` to keep a
   legacy local alias if existing code/tests reference the old name).
3. Remove the runner's old local definition.

### Common pitfalls

- **group_vars not loaded**: `group_vars/<name>.yml` must match an inventory
  group. Verify with `ansible-inventory --list`.
- **`changed_when: true` on template/copy**: destroys idempotency.
- **Editing a rendered/deployed file by hand**: it carries a managed marker
  (config.yaml) or is documented as deployed (rett_config JSON). Edit the
  source under `benchmark/config/` and re-run the playbook.
- **Committing `.vault_pass` or `vault/secrets.yml`**: both gitignored.
- **Using `SWAP` with empty body to delete lines in `edit`**: use the `DEL`
  form instead; empty-body `SWAP` leaves a literal `DEL` token.
- **Don't move poll constants into `defaults.py`**: they belong in
  `core/pipeline_client.py` (monkeypatch contract). Deduplicate by importing.

## Performance Notes

- Playbook renders 4 small files locally in ~2 s (Ansible startup-dominated).
  `gather_facts: false` skips fact collection.
- `defaults.py` is a plain module — zero runtime cost; imported once per
  runner process.
- Idempotent rendering means CI can re-run harmlessly.

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| ansible-core | 2.19.11 | Playbook engine, `template`/`copy`/`file`, `ansible-vault` |
| Jinja2 | (bundled) | Template rendering (`config.yaml.j2`, `.env.j2`) |
| PyYAML | (bundled) | YAML vars + vault parsing |
| benchmark.core.paths | (internal) | `BENCHMARK_ROOT` for path resolution in `defaults.py` |

Install via `uv tool install ansible-core`. `defaults.py` is pure stdlib +
`benchmark.core.paths`.

## Testing

```bash
# 1. Playbook syntax
$ ansible-playbook playbooks/deploy-config.yml --syntax-check

# 2. Render + idempotency
$ ansible-playbook playbooks/deploy-config.yml
$ ansible-playbook playbooks/deploy-config.yml | tail -1   # changed=0

# 3. Rendered file configs load correctly
$ cd ../datasets/rett_annotation && .venv/bin/python -c "
import sys; sys.path.insert(0,'src'); from config import get_config
c=get_config(); assert c.llm.model and c.llm.api_key and c.mineru_token; print('OK', c.llm.model)"
$ cd /data/[redacted-user]/Projects/01_ACMG_Lingua && uv run --project backend python -c "
import sys; sys.path.insert(0,'.')
from benchmark.runners.literature_rett import load_config, CONFIG_FILE
cfg=load_config(CONFIG_FILE); assert cfg.queries and cfg.max_results==10; print('OK', len(cfg.queries),'queries')"

# 4. Runtime constants resolve in every runner (no import errors)
$ uv run --project backend python -c "
import sys; sys.path.insert(0,'.')
import importlib
for m in ['benchmark.config.defaults','benchmark.runners.pipeline_e2e','benchmark.runners.clingen_preprocess','benchmark.runners.phase2_batch','benchmark.runners.benchmark_b_phase2_sample','benchmark.runners.filter_variant_evidence','benchmark.runners.literature_rett']: importlib.import_module(m)
print('all runners import OK')"

# 5. Full benchmark test suite
$ cd backend && uv run pytest tests/benchmark/ -q
```

What is **not** covered: multi-host deployment (local-only by design), vault
password rotation (requires re-encrypting `vault/secrets.yml`).

## See also

- `benchmark/config/__init__.py` — the scope boundary docstring (which config
  lives where).
- `benchmark/core/pipeline_client.py` — canonical poll/retry constants +
  `submit_and_poll` monkeypatch contract.
- `benchmark/core/paths.py` — canonical filesystem roots.
- `lesson.md` (2026-06-19) — the `SWAP`-empty-body `DEL` token footgun, the
  group_vars/inventory binding trap, and the stale `CONFIG_FILE` default.
