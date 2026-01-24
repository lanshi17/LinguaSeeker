#!/usr/bin/env python3
"""Main entry point for ACMG PS3 Evidence Extraction Pipeline."""

import sys

from src.app import main


if __name__ == "__main__":
    try:
        exit_code = main()
    except KeyboardInterrupt:
        print("Interrupted by user.")
        exit_code = 130
    except Exception as exc:  # pragma: no cover - defensive
        print(f"Unexpected error: {exc}", file=sys.stderr)
        exit_code = 1
    sys.exit(exit_code)

