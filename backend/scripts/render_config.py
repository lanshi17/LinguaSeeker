#!/usr/bin/env python3
"""Render configuration from layered YAML files.

Loads defaults/main.yaml, environments/<env>.yaml, and vault/<env>.yaml,
merges them (with later files overriding earlier ones), and renders the
Jinja2 template to produce the flat config-dev.yaml format.

Usage:
    uv run python scripts/render_config.py --env development
    uv run python scripts/render_config.py --env production --output config-dev.yaml
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("Error: PyYAML is required. Install with: uv add pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    from jinja2 import Environment, FileSystemLoader
except ImportError:
    print("Error: Jinja2 is required. Install with: uv add jinja2", file=sys.stderr)
    sys.exit(1)


BACKEND_ROOT = Path(__file__).resolve().parent.parent
CONFIG_ROOT = BACKEND_ROOT / "config"


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override dict into base dict.
    
    Nested dicts are merged; all other values are replaced.
    """
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_layered_config(environment: str) -> dict:
    """Load and merge configuration from layered YAML files.
    
    Loading order (lowest to highest priority):
      1. defaults/main.yaml
      2. environments/<environment>.yaml
      3. vault/<environment>.yaml (optional, git-ignored)
    """
    merged = {}
    
    # Layer 1: defaults/main.yaml (required)
    defaults_path = CONFIG_ROOT / "defaults" / "main.yaml"
    if defaults_path.exists():
        with open(defaults_path) as f:
            defaults = yaml.safe_load(f) or {}
        merged = deep_merge(merged, defaults)
    else:
        print(f"Warning: {defaults_path} not found", file=sys.stderr)
    
    # Layer 2: environments/<env>.yaml (optional)
    env_path = CONFIG_ROOT / "environments" / f"{environment}.yaml"
    if env_path.exists():
        with open(env_path) as f:
            env_config = yaml.safe_load(f) or {}
        merged = deep_merge(merged, env_config)
    else:
        print(f"Info: {env_path} not found, using defaults only", file=sys.stderr)
    
    # Layer 3: vault/<env>.yaml (optional, secrets)
    vault_path = CONFIG_ROOT / "vault" / f"{environment}.yaml"
    if vault_path.exists():
        with open(vault_path) as f:
            vault_secrets = yaml.safe_load(f) or {}
        merged = deep_merge(merged, vault_secrets)
    else:
        print(f"Info: {vault_path} not found, no secrets loaded", file=sys.stderr)
    
    return merged


def render_config_template(config_data: dict, environment: str) -> str:
    """Render the Jinja2 config template with merged configuration data."""
    template_dir = CONFIG_ROOT / "templates"
    env = Environment(
        loader=FileSystemLoader(str(template_dir)),
        keep_trailing_newline=True,
    )
    
    template = env.get_template("config.yaml.j2")
    return template.render(environment=environment, **config_data)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Render configuration from layered YAML files",
    )
    parser.add_argument(
        "--env",
        default="development",
        help="Environment name (default: development)",
    )
    parser.add_argument(
        "--output",
        help="Output file path (default: stdout)",
    )
    args = parser.parse_args()
    
    # Load layered configuration
    config_data = load_layered_config(args.env)
    
    # Render template
    rendered = render_config_template(config_data, args.env)
    
    # Write output
    if args.output:
        output_path = Path(args.output)
        if not output_path.is_absolute():
            output_path = BACKEND_ROOT / output_path
        output_path.write_text(rendered)
        print(f"Configuration rendered to {output_path}", file=sys.stderr)
    else:
        print(rendered)


if __name__ == "__main__":
    main()
