"""benchmark.config — centralized configuration home for the benchmark suite.

Two complementary mechanisms live here:

* **Ansible-managed file configs** (``ansible.cfg``, ``inventories/``,
  ``playbooks/``, ``roles/``, ``vault/``) render static/tunable config files
  (``rett_config*.json``, the Rett annotation ``config.yaml`` / ``.env``) into
  their consumer locations. Re-render with ``ansible-playbook
  playbooks/deploy-config.yml``.

* **Runtime code defaults** (``defaults.py``) is the single source of truth for
  benchmark operational constants previously duplicated across runners
  (pipeline base URL, Phase 2 status sets, filter thresholds, default I/O
  dirs, Rett seed queries, the canonical rett_config path). Import from
  ``benchmark.config.defaults``.

Pipeline poll/retry constants (``POLL_INTERVAL_S`` / ``MAX_POLL_ATTEMPTS`` /
``TERMINAL_STATUSES``) remain canonical in ``benchmark.core.pipeline_client``
because they are tied to the ``submit_and_poll`` primitive and its test
monkeypatch contract; runners import them from ``benchmark.core``.
"""
