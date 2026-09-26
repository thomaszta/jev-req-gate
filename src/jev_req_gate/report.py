"""报告输出：控制台打印与 CSV / JSON 导出。"""
from __future__ import annotations

import csv
import json
from typing import Any

from .profiles import DEFAULT_PROFILE

_TAG = {"green": "GREEN 放行", "yellow": "YELLOW 转人工", "red": "RED 打回"}


def print_result(res: dict[str, Any]) -> None:
    tag = _TAG[res["verdict"]]
    rid = res.get("id")
    head = f"[{rid} {tag}]" if rid else f"[{tag}]"
    print(f"{head} {res['text'][:60]}")
    if res["q_avg"] is not None:
        print(f"    质量均分: {res['q_avg']:.2f}   风险: {res['risk']}")
    for r in res["reasons"]:
        print(f"    - {r}")


def export_csv(path: str, results: list[dict[str, Any]], profile: list[dict[str, Any]] | None = None) -> None:
    profile = profile or DEFAULT_PROFILE
    cols = ["id", "text", "verdict", "q_avg", "risk", "reasons"] + \
           [q["key"] for q in profile if q["type"] != "choice"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in results:
            a = r["answers"]
            row = [r.get("id", ""), r["text"], r["verdict"], r["q_avg"], r["risk"], ";".join(r["reasons"])]
            for k in cols[6:]:
                v = a.get(k, {})
                row.append(v.get("noul", v.get("score", "")))
            w.writerow(row)


def export_json(path: str, results: list[dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
