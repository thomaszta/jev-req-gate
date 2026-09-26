#!/usr/bin/env python3
"""pre-commit hook: gate each changed requirement file with Jev (TypeSafe System One).

Usage:
    python hooks/jev_req_gate_hook.py path/to/requirements.json [path/to/req.txt ...]

For every given file it runs `jev-req-gate --file <file>` and fails the commit if
any requirement is BLOCKed. YELLOW (review) items are reported but don't block.

Prerequisites:
  - `jev-req-gate` installed (`pip install jev-req-gate`)
  - `TYPESAFE_API_KEY` set in the environment (or passed as `--api-key`)

Register it in `.pre-commit-config.yaml` (see the repo root) or via the hook id
below from this repository.
"""
from __future__ import annotations

import os
import sys


def main(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write("usage: jev_req_gate_hook.py <req files...>\n")
        return 1

    try:
        from jev_req_gate.cli import main as gate_main
    except ImportError:
        sys.stderr.write(
            "jev-req-gate is not installed. Run: pip install jev-req-gate\n"
        )
        return 1

    api_key = os.environ.get("TYPESAFE_API_KEY")
    if not api_key:
        sys.stderr.write(
            "TYPESAFE_API_KEY is not set. The gate cannot run without it.\n"
        )
        return 1

    # each file is gated individually so per-file reports are clear
    failed = False
    for path in argv:
        if not os.path.exists(path):
            sys.stderr.write(f"[skip] {path}: file not found\n")
            continue
        sys.stderr.write(f"\n=== gating {path} ===\n")
        code = gate_main(["--file", path])
        if code != 0:  # 1 = at least one BLOCK, 2 = usage/dependency error
            failed = True

    if failed:
        sys.stderr.write(
            "\n[jev-req-gate] blocked requirement(s) detected — fix them before committing.\n"
        )
        return 1
    sys.stderr.write("\n[jev-req-gate] no blocked requirements.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
