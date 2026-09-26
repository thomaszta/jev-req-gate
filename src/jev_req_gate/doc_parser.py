"""文档适配层：把整篇需求文档(.md/.txt)拆解为带编号的条目 + 上下文。

定位：拆解是"输入转换"，不是质量判断——由可复现的启发式规则完成，
输出可人工确认的 prepared.json（HITL）；Jev 仍只做判断。

语义修正：拆解后的"条目化全文"作为 document 喂给 state，
替代先前"按行碎片"的 document，让 contradicts_siblings 有完整条目级上下文。
"""
from __future__ import annotations

import re
from typing import Any

# 条目识别
_NUM_ITEM = re.compile(r"^\s*(\d+(?:\.\d+)*)\)?[.、]?\s+(?=\S)(.+)$")        # 1. / 2.1 / 1）xxx
_ALPHA_ITEM = re.compile(r"^\s*([A-Za-z]{1,}[-_]?\d+)\s*[:.\s]\s*(?=\S)(.+)$")  # R01 / REQ-01: / FR-2
_STORY_ITEM = re.compile(                                                      # 故事/US-2 目标行
    r"^\s*(?:用户?故事|故事|用户场景|场景|用例|use\s*case|scenario|story)"
    r"\s*[:：]?\s*(?:\d+)?[\s:：]*[，,;；]?(?=\S)(.+)$", re.I)
_MD_ITEM = re.compile(r"^\s*[-*+]\s+(?:\[[ xX]\]\s+)?(?=\S)(.+)$")            # - xxx / - [ ] xxx
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s+(.+)$")
_TABLE_ROW = re.compile(r"^\s*\|")
_TABLE_SEP = re.compile(r"^\s*\|[\s:|-]+\|?\s*$")
_CLEAN = re.compile(r"[*_`]+")
# 表格占位噪声：单独出现的占位符不构成需求条目
_NOISE_CELL = {"略", "无", "暂无", "待定", "-", "/", "—", "…", "...", "n/a", "na", "tbd",
               "不适用", "无要求", "无验收", ""}


def _clean_text(t: str) -> str:
    return " ".join(_CLEAN.sub("", t).split())


def _next_id(i: int) -> str:
    return f"R{i:02d}"


def split(text: str) -> dict[str, Any]:
    """把整篇文档拆解为 items / document / context_text。

    items:      [{"id","text","source_ref"}]，按文档顺序编号 R01…
    document:   段落级列表（背景段落 + 每条目全文），供 state.document
    context_text: 背景/非条目文本（可作 project_context 缺省值）
    """
    raw_lines = text.splitlines()
    items: list[dict[str, Any]] = []
    context_lines: list[str] = []
    doc_paras: list[str] = []
    skipped: list[str] = []

    # 第一遍：预扫描标题，识别"需求类章节"（该章节下普通列表也当条目）
    in_requirement_section = False
    section: str | None = None
    buf: list[str] = []          # 当前条目续行
    cur_item: dict[str, Any] | None = None
    cur_ref: str | None = None

    def flush_item() -> None:
        nonlocal cur_item, cur_ref, buf
        if cur_item is not None:
            t = " ".join([cur_item["text"]] + [_clean_text(b) for b in buf]).strip()
            if t:
                cur_item["text"] = t
                items.append(cur_item)
            else:
                skipped.append(str(cur_ref))
        cur_item = None
        cur_ref = None
        buf = []

    for idx, line in enumerate(raw_lines):
        s = line.rstrip()
        if not s.strip():
            continue

        m = _HEADING.match(s)
        if m:
            flush_item()
            title = _clean_text(m.group(1))
            section = title
            in_requirement_section = bool(
                re.search(r"需求|要求|requirement|feature|功能|story|用例|use\s*case|验收|acceptance", title, re.I))
            doc_paras.append(title)
            context_lines.append(title)
            continue

        m = _NUM_ITEM.match(s)
        if m:
            flush_item()
            ref, body = m.group(1), _clean_text(m.group(2))
            cur_item = {"id": _next_id(len(items) + 1), "text": body, "source_ref": ref}
            cur_ref = ref
            continue
        m = _ALPHA_ITEM.match(s)
        if m:
            flush_item()
            ref, body = m.group(1), _clean_text(m.group(2))
            cur_item = {"id": _next_id(len(items) + 1), "text": body, "source_ref": ref}
            cur_ref = ref
            continue
        m = _STORY_ITEM.match(s)
        if m:
            # 用户故事目标行：开新条目（而非并入上一条续行），body 可能为空的标题行
            flush_item()
            body = _clean_text(m.group(1))
            if body:
                cur_item = {"id": _next_id(len(items) + 1), "text": body,
                            "source_ref": f"story-{len(items) + 1}"}
                cur_ref = f"story-{len(items) + 1}"
            continue
        m = _MD_ITEM.match(s)
        if m:
            flush_item()
            cur_item = {"id": _next_id(len(items) + 1), "text": _clean_text(m.group(1)),
                        "source_ref": f"list-{len(items) + 1}"}
            cur_ref = f"list-{len(items) + 1}"
            continue

        if _TABLE_ROW.match(s):
            flush_item()
            # 表头行（紧随分隔行）跳过；分隔行本身跳过
            nxt = raw_lines[idx + 1].strip() if idx + 1 < len(raw_lines) else ""
            if _TABLE_SEP.match(s) or (nxt and _TABLE_SEP.match(nxt)):
                continue
            cells = [c.strip() for c in s.strip().strip("|").split("|")]
            cells = [_clean_text(c) for c in cells if c]
            # 过滤占位噪声（"略"/"无"/"-"等）：整行只剩噪声时不拆成条目
            valid = [c for c in cells if c.lower() not in _NOISE_CELL]
            if len(valid) >= 2:
                items.append({"id": _next_id(len(items) + 1), "text": " ".join(valid),
                              "source_ref": f"table-{len(items) + 1}"})
            else:
                context_lines.append(s)
            continue

        # 普通行：编号条目的续行，或上下文段落
        if cur_item is not None:
            buf.append(s)
        else:
            context_lines.append(s)

    flush_item()

    # 组装 document：背景段落 + 每条目全文（条目级，非行碎片）
    doc_paras = doc_paras + [it["text"] for it in items] \
        if not doc_paras else doc_paras + [it["text"] for it in items]
    # 背景段落（非条目、非标题的行）归入 document 前部
    ctx = [_clean_text(c) for c in context_lines if _clean_text(c)]
    document: list[str] = []
    if ctx:
        document.append("\n".join(ctx[:20]))
    document += [it["text"] for it in items]

    return {
        "title": doc_paras[0] if doc_paras else None,
        "items": items,
        "document": document,
        "context_text": "\n".join(ctx),
        "skipped": skipped,
    }


def write_prepared(path: str, parsed: dict[str, Any]) -> str:
    """把拆解结果写成 prepared.json（人工确认后 --prepared 复用）。"""
    out = {
        "title": parsed.get("title"),
        "items": parsed["items"],
        "context_text": parsed.get("context_text", ""),
        "document": parsed.get("document", []),
    }
    with open(path, "w", encoding="utf-8") as f:
        import json
        json.dump(out, f, ensure_ascii=False, indent=2)
    return path
