# benchmark/config — Ansible-managed benchmark configuration

> Centralized, Ansible-managed configuration for the benchmark subproject. Scattered
> benchmark config files are collected here as the single source of truth and rendered
> in place by an Ansible playbook. Consumer code reads from its original locations
> unchanged — this module owns the *source*, not the *load path*.

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

# 3. Render configs into the Rett annotation tool
ansible-playbook playbooks/deploy-config.yml
# → writes benchmark/datasets/rett_annotation/{config.yaml, .env}
```

Re-running the playbook reports `changed=0` when nothing changed — it is idempotent.

## Architecture

`benchmark/config/` is a **template-rendering pipeline**, not a runtime module.
Variables flow from two sources through Jinja2 templates into the consumer's
original file locations:

```
                ┌─────────────────────────────┐
                │   inventories/local/         │
                │   group_vars/benchmark.yml   │  non-secret vars
                │   (rett_annotation_*)        │  (llm, pdf_parser, …)
                └──────────────┬───────────────┘
                               │
   ┌───────────────────────────┼───────────────────────────┐
   │   playbooks/deploy-config.yml                          │
   │   vars_files: ../vault/secrets.yml                     │
   │   role: rett_annotation_config                         │
   └───────────────┬───────────────────────────────────────┘
                   │
   ┌───────────────┼───────────────────┐
   │   roles/rett_annotation_config/   │
   │   tasks/main.yml                  │
   │   templates/{config.yaml.j2,.env.j2}
   └───────┬───────────────────┬───────┘
           │                   │
           ▼                   ▼
  config.yaml (0644)    .env (0600, no_log)
   non-secrets          secrets from vault/secrets.yml
           │                   │
           └─────────┬─────────┘
                     ▼
        benchmark/datasets/rett_annotation/
        read by src/config.py (Config loader)
                     │
                     ▼
        rett_annotation tool (annotator, pdf_parser, …)
```

Two deliberately separated variable sources:

| Source | File | Holds | Encrypted? |
|--------|------|-------|------------|
| Non-secret vars | `inventories/local/group_vars/benchmark.yml` | LLM endpoint, parser params, paths, concurrency | No (committed) |
| Secret vars | `vault/secrets.yml` | API keys, MinerU token | Yes (`ansible-vault`) |

This split enforces project rule 16: secrets never live in committed YAML; they are
injected from the vault and rendered with `no_log: true` so they never appear in
playbook output.

## Public API

This module has no code API. Its interface is the **playbook + variable contract**.

### Entry point: `playbooks/deploy-config.yml`

```yaml
- name: Deploy Rett annotation benchmark configuration
  hosts: localhost
  connection: local
  gather_facts: false
  vars_files:
    - ../vault/secrets.yml
  roles:
    - role: rett_annotation_config
```

Run from `benchmark/config/`: `ansible-playbook playbooks/deploy-config.yml`.

### Role: `rett_annotation_config`

| Task | Module | Dest | Mode | Notes |
|------|--------|------|------|-------|
| Ensure destination directory exists | `ansible.builtin.file` | `rett_annotation_dest_root` | 0755 | idempotent |
| Render config.yaml (non-secret) | `ansible.builtin.template` | `rett_annotation_config_dest` | 0644 | idempotent via checksum |
| Render .env (secrets from vault) | `ansible.builtin.template` | `rett_annotation_env_dest` | 0600 | `no_log: true` |

### Variable contract (`group_vars/benchmark.yml`)

| Variable | Type | Purpose |
|----------|------|---------|
| `rett_annotation_dest_root` | path (templated) | Render target dir; resolves to `<repo>/benchmark/datasets/rett_annotation` |
| `rett_annotation_config_dest` | path | `{{ dest_root }}/config.yaml` |
| `rett_annotation_env_dest` | path | `{{ dest_root }}/.env` |
| `rett_annotation_llm` | dict | `base_url`, `model`, `max_tokens`, `temperature`, `timeout` |
| `rett_annotation_llm_fallback` | dict | `enabled` (bool) + same fields; block emitted only when `enabled: true` |
| `rett_annotation_pdf_parser` | dict | `backend`, `mineru_*`, `poll_interval`, `max_poll_attempts`, `batch_size` |
| `rett_annotation_annotation` | dict | `max_concurrency`, `chunk_size` |
| `rett_annotation_paths` | dict | `pdf_source_dir`, `draft_dir`, `approved_dir`, `rejected_dir`, `ground_truth_dir` |

### Secret contract (`vault/secrets.yml`)

```yaml
rett_annotation_secrets:
  llm_api_key: "…"           # → ANNOTATION_LLM_API_KEY
  llm_fallback_api_key: ""   # → ANNOTATION_LLM_FALLBACK_API_KEY (emitted only if non-empty)
  mineru_token: "…"          # → ANNOTATION_MINERU_TOKEN
```

The `.env.j2` template emits the fallback key line **only when**
`rett_annotation_secrets.llm_fallback_api_key` is non-empty — the `config.yaml.j2`
template emits the `llm_fallback:` block **only when**
`rett_annotation_llm_fallback.enabled` is true. The two switches are independent by
design (you may configure a fallback endpoint without committing a key).

## Internal Design

### Path resolution is CWD-independent

`rett_annotation_dest_root` is computed from `playbook_dir`, which Ansible resolves
to the absolute path of `benchmark/config/playbooks`:

```yaml
rett_annotation_dest_root: "{{ (playbook_dir | dirname | dirname) }}/datasets/rett_annotation"
```

`playbook_dir | dirname` → `benchmark/config`, `| dirname` → `benchmark`, so the
target is always `<repo>/benchmark/datasets/rett_annotation` regardless of where
`ansible-playbook` is invoked from. This is why the playbook is safe to run from
`benchmark/config/` even though `ansible.cfg` sets a relative inventory path.

### Inventory ↔ group_vars binding

`group_vars/benchmark.yml` is loaded **only because** `inventories/local/hosts.yml`
places `localhost` inside the `benchmark` group:

```yaml
all:
  children:
    benchmark:        # ← this group name must match group_vars/<name>.yml
      hosts:
        localhost:
          ansible_connection: local
          ansible_python_interpreter: auto_silent
```

`auto_silent` suppresses the interpreter-discovery warning. If you rename the group,
rename the `group_vars/` file to match or the vars silently go undefined (a common
Ansible footgun — see *Pitfalls* below).

### Idempotency

The `ansible.builtin.template` module computes a SHA of the rendered content and
compares it to the destination. When identical, it reports `changed=0` and does not
rewrite the file. **Do not add `changed_when: true`** to these tasks — that forces
`changed=1` on every run and defeats the point (this was a bug during initial
development; see `lesson.md` 2026-06-19).

### Vault wiring

`ansible.cfg` declares `vault_password_file = .vault_pass`, so `ansible-playbook`
auto-decrypts `vault/secrets.yml` without a `--vault-password-file` flag on every
invocation. The playbook loads it explicitly via `vars_files: ../vault/secrets.yml`
so the `rett_annotation_secrets` dict is in scope for the role's templates.

### Consumer loader (unchanged)

`benchmark/datasets/rett_annotation/src/config.py` reads the rendered files — this
module never touches the loader:

```python
_ANNOTATION_ROOT = Path(__file__).resolve().parent.parent
# Config.__init__:
config_path = config_path or (_ANNOTATION_ROOT / "config.yaml")
# AnnotationSettings:
env_file=str(_ANNOTATION_ROOT / ".env"), env_prefix="ANNOTATION_"
```

Because we render to exactly those paths, no source code change was required.

## Usage Patterns

### Change the LLM model / endpoint

Edit non-secret values, then re-render:

```bash
# inventories/local/group_vars/benchmark.yml
#   rett_annotation_llm:
#     model: "claude-opus-4-8"
$ ansible-playbook playbooks/deploy-config.yml
```

### Rotate a secret

```bash
$ ansible-vault edit vault/secrets.yml
# edit rett_annotation_secrets.llm_api_key
$ ansible-playbook playbooks/deploy-config.yml
```

### Enable the fallback LLM provider

Two independent switches must both be set:

```yaml
# group_vars/benchmark.yml
rett_annotation_llm_fallback:
  enabled: true              # emits llm_fallback: block in config.yaml
  # …
# vault/secrets.yml
rett_annotation_secrets:
  llm_fallback_api_key: "sk-…"  # non-empty → emits ANNOTATION_LLM_FALLBACK_API_KEY
```

### Verify a fresh checkout produces the same config

```bash
$ ansible-playbook playbooks/deploy-config.yml
$ diff <(ansible-playbook playbooks/deploy-config.yml --check 2>&1 | grep changed) "changed=0"
```

Or just run twice and confirm the second run shows `changed=0`.

### Inspect rendered variables without writing files

```bash
$ ansible-inventory --list | python3 -c "import json,sys;print(json.load(sys.stdin)['_meta']['hostvars']['localhost']['rett_annotation_llm'])"
```

## Extension Guide

### Add a new managed config target (e.g. another benchmark dataset tool)

1. **Add vars** in `group_vars/benchmark.yml` under a new prefix, e.g.
   `newtool_*`, including a `newtool_dest_root` templated from `playbook_dir`.
2. **Add secrets** to `vault/secrets.yml` under a new top-level key, e.g.
   `newtool_secrets:`. Add the same key to `vault/secrets.example.yml` as a
   placeholder.
3. **Create a role**: `roles/newtool_config/{tasks/main.yml,templates/*.j2}`.
   Mirror `rett_annotation_config` — `file` for the dir, `template` (0644) for
   non-secrets, `template` (0600, `no_log: true`) for secrets.
4. **Add the role** to `playbooks/deploy-config.yml` under `roles:`.
5. **Re-render** and verify idempotency.

### Common pitfalls

- **group_vars not loaded**: the `group_vars/<name>.yml` filename must equal an
  inventory group name. Verify with
  `ansible-inventory --list` and check `hostvars.localhost` contains your vars.
- **`changed_when: true` on template tasks**: destroys idempotency. Let the
  template module's checksum comparison do its job.
- **Committing `.vault_pass` or `vault/secrets.yml`**: both are in `.gitignore`.
  After editing `.gitignore`, confirm with
  `git check-ignore -v benchmark/config/.vault_pass benchmark/config/vault/secrets.yml`.
- **Editing the rendered file by hand**: it carries a `Managed by Ansible` header
  and will be overwritten on the next render. Edit the source (group_vars / vault)
  and re-run the playbook.
- **Hashline-editing YAML inventory**: when using the `edit` tool on `hosts.yml`,
  a `SWAP` range must cover every line you change or you'll leave duplicate lines.
  For multi-line structural edits, prefer `write` to rewrite the whole file.

## Performance Notes

- The playbook renders two small files locally — runtime is ~1–2 s, dominated by
  Ansible startup, not rendering. No perf concerns at this scale.
- `gather_facts: false` skips fact collection (unnecessary for local file render)
  and shaves startup time.
- Idempotency means CI can re-run harmlessly; only an actual diff writes the file
  (and would trigger downstream tool reload on next run).

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| ansible-core | 2.19.11 | Playbook engine, `template`/`file` modules, `ansible-vault` |
| Jinja2 | (bundled w/ ansible-core) | Template rendering (`config.yaml.j2`, `.env.j2`) |
| PyYAML | (bundled w/ ansible-core) | YAML vars + vault file parsing |

Install via `uv tool install ansible-core` (project rule 1: no system pip). No
Python or Rust runtime dependency — the rendered artifacts are plain YAML + dotenv.

## Testing

There is no unit-test framework for this module (Ansible playbooks are validated
by execution). The verification protocol is:

```bash
# 1. Syntax check the playbook
$ ansible-playbook playbooks/deploy-config.yml --syntax-check

# 2. Render
$ ansible-playbook playbooks/deploy-config.yml

# 3. Idempotency — second run must report changed=0
$ ansible-playbook playbooks/deploy-config.yml | tail -1

# 4. Consumer reads rendered files correctly
$ cd ../datasets/rett_annotation && .venv/bin/python -c "
import sys; sys.path.insert(0,'src')
from config import get_config
c=get_config()
assert c.llm.model and c.llm.api_key and c.mineru_token
print('OK', c.llm.model)
"

# 5. Secrets never leak into output (no_log)
$ ansible-playbook playbooks/deploy-config.yml -v 2>&1 | grep -i api_key || echo "no leak"
```

What is **not** covered: multi-host deployment (this is local-only by design), and
rotation of the vault password itself (requires re-encrypting `vault/secrets.yml`).

## See also

- `lesson.md` (2026-06-19) — the group_vars/inventory binding footgun and the
  `changed_when` idempotency bug, with prevention notes.
- `benchmark/datasets/rett_annotation/src/config.py` — the consumer loader
  (reads the rendered files; unchanged by this module).
- `docs/active/2026-06-18-benchmark-framework-refactor-plan.md` — the broader
  benchmark refactor that motivated centralizing this config.
