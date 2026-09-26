#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
免安装的顶层入口（与包名不冲突，避免遮蔽 bug）：
    python reqgate.py --demo good
安装后可改用 `jev-req-gate` 或 `python -m jev_req_gate`。
"""
import os
import sys

_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from jev_req_gate.cli import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
