#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
需求质量门禁对比基准：在同一测试集上，真实采集 Jev 与(可选)通用 LLM 的判定。

本脚本同时支持两个后端，跑同一份 benchmarks/test_set.json，输出对称对比：
  - jev : 真实调用 TypeSafe System One（本环境可直接跑，采集真实数据）
  - llm : OpenAI 兼容的通用 LLM（需 OPENAI_API_KEY / OPENAI_BASE_URL，待 key 补跑）

用法：
  python benchmarks/benchmark.py --backend jev [--runs 2] [--out benchmarks/report_jev.json]
  OPENAI_API_KEY=xx OPENAI_BASE_URL=xx python benchmarks/benchmark.py --backend llm --model gpt-4o-mini

指标口径（HITL 三态，与 docs/methodology.md 一致）：
  - Jev verdict: green=自动放行 / yellow=转人工 / red=自动打回
  - LLM 二态映射到同一语义: pass→放行(green)，block→打回(red)，无转人工档
  - 拦截率(坏需求非放行): expected=block 且 majority_verdict≠green
  - 自动打回: expected=block 且 verdict=red
  - 误打回(好): expected=pass 且 verdict=red
  - 自动放行(好): expected=pass 且 verdict=green
  - 成本: Jev 按 $0.042/MTok 输入(输出免费)估算；LLM 需 --input-price/--output-price
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if os.path.join(REPO, "src") not in sys.path:
    sys.path.insert(0, os.path.join(REPO, "src"))

JEV_INPUT_PRICE_PER_MT = 0.042  # 美元/百万 token，官方口径(输出免费)

_LLM_PROMPT = (
    "你是一个需求质量评审。对下面这条需求，从「表述无歧义、内容自足、正确、可行、必要、"
    "不与他人矛盾、符合规范」判断它应被 放行(pass) 还是 打回(block)。"
    "只输出 JSON：{{\"verdict\": \"pass\"|\"block\", \"reason\": \"一句话理由\"}}。\n"
    "项目上下文：{context}\n需求：{text}"
)


def _load_test_set(path: str) -> tuple[str, list[dict]]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data["_meta"]["context"], data["requirements"]


# ---------------------------------------------------------------------------
# 后端：Jev（真实）
# ---------------------------------------------------------------------------
def _run_jev(text: str, context: str) -> dict:
    from jev_req_gate.core import build_state, decide, make_questions, normalize_sdk_response
    from jev_req_gate.profiles import DEFAULT_THRESHOLDS
    from typesafe_sdk import TypeSafeClient

    t0 = time.time()
    with TypeSafeClient() as client:
        resp = client.system_one(
            model="jev-latest",
            state=build_state(text, project_context=context),
            questions=make_questions(),
        )
    latency = time.time() - t0
    answers = normalize_sdk_response(resp)
    verdict, reasons, _ = decide(answers, DEFAULT_THRESHOLDS)
    inp = int(getattr(resp.usage, "input_tokens", 0))
    out = int(getattr(resp.usage, "output_tokens", 0))
    return {"verdict": verdict, "reasons": reasons, "answers": answers, "latency": latency,
            "input_tokens": inp, "output_tokens": out,
            "cost": inp / 1e6 * JEV_INPUT_PRICE_PER_MT, "backend": "jev"}


# ---------------------------------------------------------------------------
# 后端：OpenAI 兼容 LLM（待 key）
# ---------------------------------------------------------------------------
def _run_llm(text: str, context: str, model: str, in_price: float, out_price: float) -> dict:
    key = os.environ.get("OPENAI_API_KEY")
    base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    if not key:
        raise SystemExit("LLM 后端需要 OPENAI_API_KEY（可加 OPENAI_BASE_URL 指向任意兼容端点）")
    body = {
        "model": model,
        "temperature": 0,
        "messages": [{"role": "user", "content": _LLM_PROMPT.format(context=context, text=text)}],
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    t0 = time.time()
    with urllib.request.urlopen(req, timeout=120) as r:
        data = json.loads(r.read().decode())
    latency = time.time() - t0
    content = data["choices"][0]["message"]["content"]
    try:
        parsed = json.loads(content)
        verdict = parsed.get("verdict", "block")  # 解析失败按保守 block
    except Exception:
        verdict = "block"
    usage = data.get("usage", {})
    inp = int(usage.get("prompt_tokens", 0))
    out = int(usage.get("completion_tokens", 0))
    return {"verdict": verdict, "reasons": [content[:120]], "latency": latency,
            "input_tokens": inp, "output_tokens": out,
            "cost": inp / 1e6 * in_price + out / 1e6 * out_price, "backend": "llm"}


# ---------------------------------------------------------------------------
# 聚合
# ---------------------------------------------------------------------------
def _verdict_is_block(verdict: str) -> bool:
    return verdict == "red" or verdict == "block"


def main() -> int:
    p = argparse.ArgumentParser(description="Jev vs LLM 需求质量门禁对比基准")
    p.add_argument("--backend", choices=["jev", "llm"], required=True)
    p.add_argument("--test-set", default=os.path.join(REPO, "benchmarks/test_set.json"))
    p.add_argument("--runs", type=int, default=1, help="每条需求重复次数(测稳定性)")
    p.add_argument("--model", default="gpt-4o-mini", help="LLM 模型名")
    p.add_argument("--input-price", type=float, default=0.15, help="LLM 输入价 美元/MTok")
    p.add_argument("--output-price", type=float, default=0.60, help="LLM 输出价 美元/MTok")
    p.add_argument("--out", help="结果输出 JSON 路径")
    args = p.parse_args()

    context, reqs = _load_test_set(args.test_set)

    results = []
    for req in reqs:
        row = {"id": req["id"], "expected": req["expected"], "runs": []}
        for _ in range(args.runs):
            r = _run_jev(req["text"], context) if args.backend == "jev" else \
                _run_llm(req["text"], context, args.model, args.input_price, args.output_price)
            row["runs"].append(r)
        row["consistent"] = len({r["verdict"] for r in row["runs"]}) == 1
        results.append(row)

    # ---- 聚合指标（HITL 口径：green=自动放行 / yellow=转人工 / red=自动打回）----
    # LLM 二态映射到同一语义：pass→放行(green)，block→打回(red)，无转人工档。
    def _majority(vs):
        return max(set(vs), key=vs.count)

    for r in results:
        r["majority_verdict"] = _majority([x["verdict"] for x in r["runs"]])
    n_pass = sum(1 for r in results if r["expected"] == "pass")
    n_block = sum(1 for r in results if r["expected"] == "block")
    bad = [r for r in results if r["expected"] == "block"]
    good = [r for r in results if r["expected"] == "pass"]
    # 语义归一化：Jev 用 red/yellow/green，LLM 用 block/pass（无 yellow）
    RED = ("red", "block")
    GRN = ("green", "pass")
    intercepted = sum(1 for r in bad if r["majority_verdict"] not in GRN)  # 坏需求被拦下
    auto_block = sum(1 for r in bad if r["majority_verdict"] in RED)       # 坏需求被自动打回
    false_block = sum(1 for r in good if r["majority_verdict"] in RED)     # 好需求被误打回
    auto_pass = sum(1 for r in good if r["majority_verdict"] in GRN)       # 好需求被自动放行
    review = sum(1 for r in results if r["majority_verdict"] == "yellow")  # 转人工
    consistency = sum(1 for r in results if r["consistent"])
    lats = [r["latency"] for rr in results for r in rr["runs"]]
    tokens_in = sum(r["input_tokens"] for rr in results for r in rr["runs"])
    tokens_out = sum(r["output_tokens"] for rr in results for r in rr["runs"])
    cost = sum(r["cost"] for rr in results for r in rr["runs"])

    report = {
        "backend": args.backend, "model": args.model if args.backend == "llm" else "jev-latest",
        "test_set": os.path.basename(args.test_set), "n": len(reqs),
        "runs_per_item": args.runs,
        "intercept_recall": round(intercepted / n_block, 4) if n_block else None,
        "auto_block_recall": round(auto_block / n_block, 4) if n_block else None,
        "auto_pass_rate": round(auto_pass / n_pass, 4) if n_pass else None,
        "false_block_rate": round(false_block / n_pass, 4) if n_pass else None,
        "review_rate": round(review / len(reqs), 4) if reqs else None,
        "consistency": round(consistency / len(reqs), 4) if reqs else None,
        "latency_p50": round(statistics.median(lats), 3) if lats else None,
        "latency_p95": round(sorted(lats)[int(0.95 * len(lats))], 3) if lats else None,
        "tokens_input": tokens_in, "tokens_output": tokens_out,
        "total_cost_usd": round(cost, 6),
    }

    print(f"后端: {report['backend']} | 测试集 {report['test_set']} | {report['n']} 条 × {report['runs_per_item']} 次")
    print(f"  [HITL] 拦截率(坏需求非放行)={report['intercept_recall']}  自动打回={report['auto_block_recall']}  "
          f"误打回(好)={report['false_block_rate']}  自动放行(好)={report['auto_pass_rate']}  转人工率={report['review_rate']}")
    print(f"  判定一致性={report['consistency']}  延迟 p50={report['latency_p50']}s  p95={report['latency_p95']}s  "
          f"token(入/出)={tokens_in}/{tokens_out}  总成本=${report['total_cost_usd']}")

    print("  逐条判定:")
    for r in results:
        v = r["majority_verdict"]
        ok = "✔" if (r["expected"] == "block" and v not in GRN) or (r["expected"] == "pass" and v in GRN) else "✘"
        print(f"    {r['id']} [{r['expected']}] -> {v.upper()} {ok}")

    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump({"report": report, "details": results}, f, ensure_ascii=False, indent=2)
        print(f"已保存: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
