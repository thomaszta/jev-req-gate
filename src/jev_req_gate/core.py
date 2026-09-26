"""核心逻辑：问题组装、state 打包、5 面综合路由、SDK 响应归一化。"""
from __future__ import annotations

import statistics
from typing import Any

try:
    from typesafe_sdk import Choice, Noul, Score, TypeSafeClient
    _SDK_AVAILABLE = True
except ImportError:
    _SDK_AVAILABLE = False

    class _SdkMissing:
        """占位：未安装 SDK 时给出友好提示，不影响 --demo / 纯路由判定。"""
        def __init__(self, *args: Any, **kwargs: Any):
            raise SystemExit(
                "未安装 typesafe-sdk，请先运行: pip install typesafe-sdk，"
                "并用真实 API key 调用；--demo 演示无需 SDK。"
            )

    Choice = Noul = Score = TypeSafeClient = _SdkMissing  # type: ignore[assignment]

from .profiles import CORE_SCORES, DEFAULT_PROFILE, DEFAULT_THRESHOLDS, human_note, human_short


# ---------------------------------------------------------------------------
# 问题组装 / state 打包
# ---------------------------------------------------------------------------
def make_questions(profile: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """把 profile 转成 typesafe_sdk 的 questions dict。"""
    profile = profile or DEFAULT_PROFILE
    questions: dict[str, Any] = {}
    for q in profile:
        t = q["type"]
        if t == "score":
            questions[q["key"]] = Score(instructions=q["instructions"], criteria=q["criteria"])
        elif t == "choice":
            questions[q["key"]] = Choice(instructions=q["instructions"], criteria=q["criteria"])
        else:  # noul
            questions[q["key"]] = Noul(instructions=q["instructions"])
    return questions


def build_state(
    text: str,
    project_context: str | None = None,
    existing: list[str] | None = None,
    document: list[str] | None = None,
    archived: str | None = None,
) -> str | dict[str, Any]:
    """把需求 + 参照上下文打包成 state（带参照时为 JSON 对象）。"""
    state: dict[str, Any] = {"requirement": text}
    if project_context:
        state["project_context"] = project_context
    if existing:
        state["existing_requirements"] = existing
    if document:
        state["document"] = document
    if archived:
        state["archived"] = archived
    return state


# ---------------------------------------------------------------------------
# 路由判定（5 面综合）
# ---------------------------------------------------------------------------
def _noul_value(answers: dict[str, Any], key: str) -> float | None:
    v = answers.get(key)
    return v.get("noul") if isinstance(v, dict) else None


def decide(
    answers: dict[str, Any],
    thresholds: dict[str, Any] | None = None,
    profile: list[dict[str, Any]] | None = None,
) -> tuple[str, list[str], dict[str, Any]]:
    """返回 (verdict, reasons, detail)。verdict: green|yellow|red

    answers 为归一化结构：{key: {"noul":..} | {"score":..,"confidence":..} | {"choice":..}}
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS
    profile = profile or DEFAULT_PROFILE

    qscores = [
        answers[k]["score"]
        for k in CORE_SCORES
        if isinstance(answers.get(k), dict) and "score" in answers.get(k, {})
    ]
    q_avg = statistics.mean(qscores) if qscores else None

    nouls = [q for q in profile if q["type"] == "noul"]
    risk = answers.get("risk", {}).get("choice") if isinstance(answers.get("risk"), dict) else None
    block_pos_keys = thresholds.get("block_pos_keys", [])
    block_neg_keys = thresholds.get("block_neg_keys", [])  # 负向打回白名单（默认仅 contradicts_siblings）

    reasons: list[str] = []

    # ---- 红 打回（只看 Jev 最可靠的信号：正向白名单 + 负向白名单）----
    for q in nouls:
        v = _noul_value(answers, q["key"])
        if v is None:
            continue
        if q["direction"] == "positive" and q["key"] in block_pos_keys and v < thresholds["block_noul_pos"]:
            reasons.append(f"【{human_short(q['key'])}】{q['key']}={v:.2f} < {thresholds['block_noul_pos']}：{human_note(q['key'])}")
        if q["direction"] == "negative" and q["key"] in block_neg_keys and v > thresholds["block_noul_neg"]:
            reasons.append(f"【{human_short(q['key'])}】{q['key']}={v:.2f} > {thresholds['block_noul_neg']}：{human_note(q['key'])}")
    if q_avg is not None and q_avg < thresholds["block_score"]:
        reasons.append(f"【质量】质量均分 {q_avg:.2f} < {thresholds['block_score']}：整体质量极差")
    if reasons:
        return "red", reasons, {"q_avg": q_avg, "risk": risk}

    # ---- 绿 放行：无红 + 关键信号全健康（7 项）----
    # 术语低 / 个别置信度低 / risk=high 是 Jev 中文输出常态噪声，不决定绿黄，只作黄提示。
    strong: list[str] = []
    if q_avg is not None and q_avg < thresholds["green_score"]:
        strong.append(f"【质量】质量均分 {q_avg:.2f} < {thresholds['green_score']}：未达放行线")
    if (sc := _noul_value(answers, "self_contained")) is not None \
            and sc < thresholds["green_self_contained"]:
        strong.append(f"【自足性】self_contained={sc:.2f} < {thresholds['green_self_contained']}：{human_note('self_contained')}")
    if (con := _noul_value(answers, "contradicts_siblings")) is not None \
            and con > thresholds["green_contradicts_max"]:
        strong.append(f"【矛盾】contradicts_siblings={con:.2f} > {thresholds['green_contradicts_max']}：{human_note('contradicts_siblings')}")
    if (imp := _noul_value(answers, "implementation_free")) is not None \
            and imp > thresholds.get("green_impl_max", 0.6):
        strong.append(f"【方案混入】implementation_free={imp:.2f} > {thresholds.get('green_impl_max', 0.6)}：{human_note('implementation_free')}")
    for key in thresholds.get("green_keys", []):
        v = _noul_value(answers, key)
        if v is not None and v < thresholds["green_noul_min"]:
            strong.append(f"【{human_short(key)}】{key}={v:.2f} < {thresholds['green_noul_min']}：{human_note(key)}")
    if not strong:
        return "green", [], {"q_avg": q_avg, "risk": risk}

    # ---- 黄 转人工：无红但有强警告（关键信号未全健康）----
    reasons = strong
    if q_avg is not None and q_avg < thresholds["review_score"]:
        reasons.append(f"【质量】质量均分 {q_avg:.2f} < {thresholds['review_score']}：整体偏弱，建议人工确认")
    if risk == "high":
        reasons.append("【风险】风险等级=high，需人工复核")
    mid_keys: list[str] = []
    for q in nouls:
        v = _noul_value(answers, q["key"])
        if v is None:
            continue
        if thresholds["noul_mid_low"] <= v <= thresholds["noul_mid_high"]:
            mid_keys.append(q["key"])
            continue
        if q["direction"] == "positive" and v < thresholds["review_pos_weak"]:
            reasons.append(f"【{human_short(q['key'])}】{q['key']}={v:.2f} 偏低：{human_note(q['key'])}")
        if q["direction"] == "negative" and v > thresholds["review_neg_hi"]:
            reasons.append(f"【{human_short(q['key'])}】{q['key']}={v:.2f} 偏高：{human_note(q['key'])}")
    if mid_keys:
        names = "、".join(human_short(k) for k in mid_keys)
        reasons.append(f"共 {len(mid_keys)} 个维度不确定（{names}），需人工复核")
    for k in CORE_SCORES:
        c = answers.get(k, {}).get("confidence") if isinstance(answers.get(k), dict) else None
        if c is not None and c < thresholds["low_confidence"]:
            reasons.append(f"【{human_short(k)}】{k} confidence={c:.2f} 偏低：模型对这条判断信心不足")
    if reasons:
        return "yellow", reasons, {"q_avg": q_avg, "risk": risk}

    return "green", [], {"q_avg": q_avg, "risk": risk}


# ---------------------------------------------------------------------------
# SDK 响应归一化
# ---------------------------------------------------------------------------
def normalize_sdk_response(response: Any) -> dict[str, Any]:
    """把 SDK 响应归一化为 {key: {type字段}} 字典。"""
    answers: dict[str, Any] = {}
    for key, ans in response.answers.items():
        t = ans.type
        if t == "choice":
            answers[key] = {"choice": ans.choice, "confidence": ans.confidence,
                            "probabilities": getattr(ans, "probabilities", None)}
        elif t == "score":
            answers[key] = {"score": ans.score, "confidence": ans.confidence,
                            "legend": getattr(ans, "legend", None)}
        elif t == "noul":
            answers[key] = {"noul": ans.noul}
    return answers


# ---------------------------------------------------------------------------
# demo（无需 API key 的演示答案）
# ---------------------------------------------------------------------------
def demo_answers(demo_case: str) -> dict[str, Any]:
    """good | ambiguous | unrealistic。返回归一化 answers。"""
    a: dict[str, Any] = {
        "clarity": {"score": 4.5, "confidence": 0.9},
        "readability": {"score": 4.2, "confidence": 0.88},
        "atomicity": {"score": 4.3, "confidence": 0.87},
        "completeness": {"score": 4.2, "confidence": 0.85},
        "self_contained": {"noul": 0.9},
        "terminology_defined": {"noul": 0.85},
        "acceptance_quantifiable": {"noul": 0.9},
        "implementation_free": {"noul": 0.1},
        "missing_info": {"choice": "none", "confidence": 0.9},
        "correct": {"noul": 0.92},
        "feasible": {"noul": 0.9},
        "necessary": {"noul": 0.95},
        "traceable": {"noul": 0.88},
        "fidelity": {"noul": 0.9},
        "consistent_internal": {"noul": 0.93},
        "contradicts_siblings": {"noul": 0.05},
        "non_redundant": {"noul": 0.9},
        "dependencies_declared": {"noul": 0.88},
        "conforms_template": {"noul": 0.85},
        "req_type": {"choice": "feature", "confidence": 0.9},
        "priority": {"choice": "should", "confidence": 0.8},
        "risk": {"choice": "low", "confidence": 0.85},
    }
    if demo_case == "ambiguous":
        a["self_contained"] = {"noul": 0.45}
        a["clarity"] = {"score": 3.5, "confidence": 0.62}
    elif demo_case == "unrealistic":
        a["feasible"] = {"noul": 0.22}
        a["fidelity"] = {"noul": 0.4}
        a["clarity"] = {"score": 4.0, "confidence": 0.8}
    return a


# ---------------------------------------------------------------------------
# 门禁执行入口
# ---------------------------------------------------------------------------
def run_gate(
    text: str,
    context: dict[str, Any] | None = None,
    thresholds: dict[str, Any] | None = None,
    demo: str | None = None,
    client: Any = None,
    store: Any = None,
    profile: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """对一条需求执行门禁。context: {project_context, existing, document, archived}

    store 非空时启用请求缓存（store.py）：同一请求只调一次 Jev，
    之后直接读缓存，结果带 cached=True。
    """
    thresholds = thresholds or DEFAULT_THRESHOLDS
    context = context or {}
    profile = profile or DEFAULT_PROFILE

    if demo is not None:
        answers = demo_answers(demo)
        model = "(demo)"
        cached = False
    else:
        if not _SDK_AVAILABLE:
            raise SystemExit("未安装 typesafe-sdk，请先运行: pip install typesafe-sdk")
        state = build_state(text, **context)
        h = None
        if store is not None:
            from .store import request_hash
            h = request_hash(state, profile, "jev-latest")
            hit = store.cached(h)
            if hit is not None:
                answers = hit["answers"]
                model = hit["model"]
                verdict, reasons, detail = decide(answers, thresholds)
                return {"text": text, "model": model, "verdict": verdict,
                        "reasons": reasons, "q_avg": detail["q_avg"],
                        "risk": detail["risk"], "answers": answers, "cached": True}
        questions = make_questions(profile)
        response = client.system_one(
            model="jev-latest",
            state=state,
            questions=questions,
        )
        model = response.model
        answers = normalize_sdk_response(response)
        cached = False
        if store is not None:
            verdict0, reasons0, _ = decide(answers, thresholds)
            store.log(h, model, "ok", text, answers, verdict=verdict0, reasons=reasons0)

    verdict, reasons, detail = decide(answers, thresholds)
    return {"text": text, "model": model, "verdict": verdict,
            "reasons": reasons, "q_avg": detail["q_avg"],
            "risk": detail["risk"], "answers": answers, "cached": cached}
