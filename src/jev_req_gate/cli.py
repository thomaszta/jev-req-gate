"""CLI 入口：`jev-req-gate` / `python -m jev_req_gate` / 顶层 wrapper。

门禁（--text/--file/--demo）+ 缓存（--db/--cache-stats/--cache-clear）
+ 标注校准闭环（--export/--eval）。
"""
from __future__ import annotations

import argparse
import os
import sys
from typing import Any

from .core import TypeSafeClient, _SDK_AVAILABLE, run_gate
from .doc_parser import split as doc_split
from .doc_parser import write_prepared as doc_write_prepared
from .labels import evaluate as labels_evaluate
from .labels import export as labels_export
from .labels import load as labels_load
from .profiles import DEFAULT_THRESHOLDS, load_profile, load_thresholds, validate_profile
from .report import export_csv, export_json, print_result
from .store import Store

__version__ = "0.6.2"


def _load_text_list(path: str) -> list[str]:
    """加载 .json(数组)/.txt(每行) 为字符串列表。"""
    ext = os.path.splitext(path)[1].lower()
    with open(path, "r", encoding="utf-8") as f:
        if ext == ".json":
            data = __import__("json").load(f)
            return data if isinstance(data, list) else [data]
        return [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]


def _load_requirements(path: str) -> list[tuple[str, str | None]]:
    """批量待审需求。支持 .json(数组，元素可带 text/archived)/.csv/.txt。"""
    import csv
    import json

    ext = os.path.splitext(path)[1].lower()
    items: list[tuple[str, str | None]] = []
    with open(path, "r", encoding="utf-8") as f:
        if ext == ".json":
            data = json.load(f)
            if isinstance(data, list):
                for it in data:
                    if isinstance(it, str):
                        items.append((it, None))
                    else:
                        items.append((it.get("text", ""), it.get("archived")))
            elif isinstance(data, dict):
                items.append((data.get("text", ""), data.get("archived")))
        elif ext == ".csv":
            for row in csv.DictReader(f):
                items.append((row.get("text", ""), row.get("archived")))
        else:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    items.append((line, None))
    return items


def _load_prepared(path: str) -> dict[str, Any]:
    """读取人工确认过的 prepared.json（doc_parser 拆解产物）。"""
    import json
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    items = data.get("items") or []
    if not isinstance(items, list) or not items:
        raise SystemExit(f"{path} 没有可用的 items（先 --from-document 生成并确认）")
    for it in items:
        if not it.get("id"):
            it["id"] = f"R{items.index(it) + 1:02d}"
    return data


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="jev-req-gate",
                                description="用 Jev (TypeSafe System One) 给 LLM 生成的需求做质量门禁（MECE 5 面）")
    p.add_argument("--text", help="单条需求文本")
    p.add_argument("--file", help="批量待审需求文件(.json/.csv/.txt)")
    p.add_argument("--from-document", metavar="PATH",
                   help="整篇需求文档(.md/.txt)：启发式拆解+编号+门禁一站式")
    p.add_argument("--prepared", metavar="PATH",
                   help="用人工确认过的拆解结果(.prepared.json) 跑门禁（保留需求编号）")
    p.add_argument("--no-gate", action="store_true",
                   help="与 --from-document 连用：只拆解并写出 prepared.json，不跑门禁")
    p.add_argument("--project-context", help="项目背景/约束/技术栈（现实层参照）")
    p.add_argument("--existing-file", help="既有需求文件，用于非冗余判断")
    p.add_argument("--document-file", help="整篇需求文档文件，用于跨条目矛盾判断")
    p.add_argument("--archived", help="上一版归档需求（可选）")
    p.add_argument("--profile-file", help="自定义问题库 JSON")
    p.add_argument("--demo", choices=["good", "ambiguous", "unrealistic"],
                   help="无 API key 演示（不真正调用 Jev）")
    p.add_argument("--out", help="导出报告路径(.csv/.json)")
    p.add_argument("--thresholds-file", help="JSON 覆盖默认阈值")
    p.add_argument("--db", help="请求缓存 SQLite 路径（默认 ~/.jev_req_gate/cache.db，可用环境变量 JEV_REQ_GATE_DB）")
    p.add_argument("--cache-stats", action="store_true", help="打印缓存统计后退出")
    p.add_argument("--cache-clear", action="store_true", help="清空缓存后退出")
    p.add_argument("--export", metavar="PATH", help="把缓存中的判定导出为 JSONL（人工标注用），每行带空 label")
    p.add_argument("--eval", metavar="PATH", help="读回标注过的 JSONL，扫描推荐阈值（--max-error）")
    p.add_argument("--max-error", type=float, default=0.1,
                   help="eval 可接受的漏检率上限（人工 block 中被放行的比例），默认 0.1")
    p.add_argument("--version", action="version", version=f"jev-req-gate {__version__}")
    return p


def _cmd_cache_stats(store: Store) -> int:
    s = store.stats()
    print(f"缓存 {store.path}")
    print(f"  共 {s['rows']} 条判定：成功 {s['ok']} / 失败 {s['errors']}")
    if s["last_ts"]:
        import datetime
        print(f"  最近一次写入: {datetime.datetime.fromtimestamp(s['last_ts']):%Y-%m-%d %H:%M:%S}")
    return 0


def _cmd_export(store: Store, path: str) -> int:
    n = labels_export(store, path)
    if n == 0:
        print("缓存中没有成功的判定（先跑一次 --text/--file 门禁，再导出）")
        return 1
    print(f"{n} 条判定 -> {path}  把每条 label 改成 pass 或 block 后运行 --eval")
    return 0


def _cmd_eval(path: str, max_error: float) -> int:
    rows = labels_load(path)
    report = labels_evaluate(rows, max_error=max_error)
    if report["labeled"] == 0:
        print(f"{path} 没有已标注的行（共 {report['total']} 行），请先标注 label=pass|block")
        return 1
    print(f"已标注 {report['labeled']}/{report['total']} 条（block={report['n_block']} / pass={report['n_pass']}）"
          f"   与当前策略一致性 {report['agreement']}")
    print(f"\n   k(阈值倍率)  打回数   漏检率   拦截召回   误伤率")
    for s in report["sweep"]:
        mark = "  <- 推荐" if s["k"] == report["recommended_k"] else ""
        rec = "-" if s["recall"] is None else f"{s['recall']:.2f}"
        fal = "-" if s["false"] is None else f"{s['false']:.2f}"
        print(f"   {s['k']:.2f}        {s['red']:4d}    {s['error']:.2f}     {rec}      {fal}{mark}")
    k = report["recommended_k"]
    if k is None:
        if report.get("unrecoverable"):
            print(f"\n存在 Jev 判 green（自动放行）但人工标 block 的条目，任何 k 都压不下漏检率。")
            print("阈值无法修复这种情况：请检查这些条目的信号分布，或增补对应原子问题后重跑。")
        else:
            print(f"\n没有任何 k 把漏检率压到 <= {max_error}，请补标更多样本或放宽 --max-error")
        return 0
    print(f"\n推荐 k={k}：把 --thresholds-file 写成 ")
    print(json_dumps(report["recommended_thresholds"]))
    print("（k=1.0 即当前默认阈值；k>1 更严、k<1 更松）")
    return 0


def json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, indent=2)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    thresholds = dict(DEFAULT_THRESHOLDS)
    if args.thresholds_file:
        thresholds = load_thresholds(args.thresholds_file)

    profile = None
    if args.profile_file:
        profile = load_profile(args.profile_file)
        errors = validate_profile(profile)
        if errors:
            print("问题库校验失败:")
            for e in errors:
                print(f"  - {e}")
            return 2

    # ---- 缓存工具子命令 ----
    if args.cache_stats or args.cache_clear or args.export:
        with Store(args.db) as store:
            if args.cache_clear:
                n = store.clear()
                print(f"已清空缓存：{n} 条")
                return 0
            if args.cache_stats:
                return _cmd_cache_stats(store)
            if args.export:
                return _cmd_export(store, args.export)

    if args.eval:
        return _cmd_eval(args.eval, args.max_error)

    # ---- 门禁主流程 ----
    context: dict[str, Any] = {}
    if args.project_context:
        context["project_context"] = args.project_context
    if args.existing_file:
        context["existing"] = _load_text_list(args.existing_file)
    if args.document_file:
        context["document"] = _load_text_list(args.document_file)
    if args.archived:
        context["archived"] = args.archived

    client = None
    store = None
    if not args.demo and not args.no_gate:
        # --no-gate 只拆解文档，不需要 API key / SDK / 缓存
        if not _SDK_AVAILABLE:
            print("未安装 typesafe-sdk，请先: pip install typesafe-sdk")
            return 2
        client = TypeSafeClient()
        store = Store(args.db)

    results: list[dict[str, Any]] = []
    default_out: str | None = None
    if args.from_document or args.prepared:
        if args.prepared:
            prep = _load_prepared(args.prepared)
            src_name = args.prepared
        else:
            with open(args.from_document, "r", encoding="utf-8") as f:
                parsed = doc_split(f.read())
            prep_path = doc_write_prepared(args.from_document + ".prepared.json", parsed)
            src_name = args.from_document
            print(f"拆解完成：{len(parsed['items'])} 条需求 -> {prep_path}")
            for it in parsed["items"]:
                print(f"  [{it['id']}] ({it['source_ref']}) {it['text'][:48]}")
            if parsed["skipped"]:
                print(f"  未拆解 {len(parsed['skipped'])} 行（空/装饰），已跳过")
            if args.no_gate:
                print("已写出拆解结果。如对条目有增删改，编辑该 JSON 后用 --prepared 运行门禁。")
                return 0
            prep = parsed
        items = prep["items"]
        context["document"] = prep.get("document") or [it["text"] for it in items]
        if not context.get("project_context") and prep.get("context_text"):
            context["project_context"] = prep["context_text"][:800]
        for it in items:
            res = run_gate(it["text"], context, thresholds, client=client,
                           store=store, profile=profile)
            res["id"] = it.get("id") or ""
            results.append(res)
        default_out = os.path.splitext(src_name)[0] + "-report.csv"
    elif args.demo:
        results.append(run_gate("(demo)", context, thresholds, demo=args.demo))
    elif args.text:
        results.append(run_gate(args.text, context, thresholds, client=client,
                                store=store, profile=profile))
    elif args.file:
        for text, _archived in _load_requirements(args.file):
            c = dict(context)
            if _archived and not c.get("archived"):
                c["archived"] = _archived
            results.append(run_gate(text, c, thresholds, client=client,
                                    store=store, profile=profile))
    else:
        _build_parser().print_help()
        return 2

    for r in results:
        print_result(r)
        if r.get("cached"):
            print("    （判定来自缓存，未调用 Jev）")

    if args.out or default_out:
        out = args.out or default_out
        if out.endswith(".json"):
            export_json(out, results)
        else:
            export_csv(out, results, profile)
        print(f"\n报告已导出: {out}")

    blocked = sum(1 for r in results if r["verdict"] == "red")
    cached_n = sum(1 for r in results if r.get("cached"))
    extra = f"（缓存命中 {cached_n} 条）" if cached_n else ""
    print(f"\n共 {len(results)} 条: 放行={sum(1 for r in results if r['verdict']=='green')} "
          f"转人工={sum(1 for r in results if r['verdict']=='yellow')} 打回={blocked} {extra}")
    return 1 if blocked else 0


if __name__ == "__main__":
    sys.exit(main())
