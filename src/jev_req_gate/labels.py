"""标注校准闭环：export 导出待人工标注数据，eval 读回标注并扫描推荐阈值。

对标 jevclip 的 export/eval：唯一必须人工的中间带裁决被做成可操作闭环——
export 给出每条已判定需求的原文与当前判定，人工标 pass/block；
eval 在「白名单信号统一阈值倍率 k」上扫描，报每个 k 的漏检/误伤/拦截召回，
并推荐满足漏检上限的最小 k（漏检可控前提下误伤最小），可直接写回 --thresholds-file。
"""
from __future__ import annotations

import json
import os
from typing import Any

from .core import decide
from .profiles import DEFAULT_THRESHOLDS
from .store import Store

# 扫描轴：白名单打回信号 block_noul_pos（现实层 positive 信号 v < 阈值 即打回）。
# k>1 阈值更高 → 更容易打回（更严）。negative 信号（contradicts_siblings）固定不动。
SCAN_FROM, SCAN_TO, SCAN_STEP = 0.6, 1.4, 0.05
LABELS = ("pass", "block")


# ---------------------------------------------------------------------------
# export
# ---------------------------------------------------------------------------
def export(store: Store, path: str) -> int:
    """把缓存里成功的判定导出为 JSONL，每行带空 label，等待人工标注。"""
    rows = store.ok_rows()
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({
                "hash": r["hash"], "text": r["text"], "verdict": r["verdict"],
                "reasons": r["reasons"], "answers": r["answers"], "label": None,
            }, ensure_ascii=False) + "\n")
    return len(rows)


def load(path: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# eval
# ---------------------------------------------------------------------------
def _verdict_under(answers: dict[str, Any], thresholds: dict[str, Any], k: float) -> str:
    t = dict(thresholds)
    t["block_noul_pos"] = round(thresholds["block_noul_pos"] * k, 4)
    verdict, _, _ = decide(answers, t)
    return verdict


def evaluate(rows: list[dict[str, Any]], max_error: float = 0.1,
             thresholds: dict[str, Any] | None = None) -> dict[str, Any]:
    """读回标注，扫描 k，推荐漏检达标下误伤最小的 k。

    label: 'pass'=人工认为应放行；'block'=人工认为应打回。
    error=人工 block 但被 green 放行的比例（漏检）；recall=人工 block 被拦下比例；
    false=人工 pass 但被判 red 的比例（误伤）。
    推荐：漏检率 ≤ max_error 的 k 里误伤最小；误伤并列取更严的 k。
    若漏检率在任何 k 下都超限（存在 Jev 判 green 但人工标 block 的条目），
    返回 unrecoverable=True —— 阈值无法修复，需检查该条信号或增补问题。
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS
    labeled = [r for r in rows if r.get("label") in LABELS]
    blocks = [r for r in labeled if r["label"] == "block"]
    passes = [r for r in labeled if r["label"] == "pass"]
    n_block, n_pass = len(blocks), len(passes)

    # 与当前策略的一致性
    agreement = None
    if labeled:
        ok = 0
        for r in labeled:
            cur = r.get("verdict")
            want_block = r["label"] == "block"
            ok += (cur == "green") != want_block  # 人工 block 且非 green，或人工 pass 且 green
        agreement = round(ok / len(labeled), 4)

    sweep: list[dict[str, Any]] = []
    recommended: float | None = None
    k = SCAN_FROM
    while k <= SCAN_TO + 1e-9:
        intercepted = sum(1 for r in blocks if _verdict_under(r["answers"], thresholds, k) != "green")
        red_total = sum(1 for r in labeled if _verdict_under(r["answers"], thresholds, k) == "red")
        err = 1.0 - intercepted / n_block if n_block else 0.0
        recall = intercepted / n_block if n_block else None
        false = sum(1 for r in passes if _verdict_under(r["answers"], thresholds, k) == "red") / n_pass if n_pass else None
        sweep.append({"k": round(k, 2), "red": red_total,
                      "error": round(err, 4), "recall": round(recall, 4) if recall is not None else None,
                      "false": round(false, 4) if false is not None else None})
        k += SCAN_STEP

    # 推荐：漏检率达标（≤ max_error）的 k 里，误伤最小；误伤并列时取更严的 k（多拦）。
    # 没有 block 样本时无法校准拦截，不推荐。
    candidates = [s for s in sweep if s["error"] <= max_error and n_block > 0]
    if candidates:
        best = min(candidates, key=lambda s: ((s["false"] if s["false"] is not None else 0.0), -s["k"]))
        recommended = best["k"]

    rec_thresholds = None
    if recommended is not None:
        rec_thresholds = dict(thresholds)
        rec_thresholds["block_noul_pos"] = round(thresholds["block_noul_pos"] * recommended, 4)

    unrecoverable = False
    if n_block and min(s["error"] for s in sweep) > max_error:
        # 存在 Jev 判 green 但人工标 block 的条目：阈值无法修复，需要检查该条信号或增补问题。
        unrecoverable = True

    return {
        "total": len(rows), "labeled": len(labeled),
        "n_block": n_block, "n_pass": n_pass,
        "agreement": agreement,
        "sweep": sweep, "recommended_k": recommended,
        "recommended_thresholds": rec_thresholds,
        "unrecoverable": unrecoverable,
    }
