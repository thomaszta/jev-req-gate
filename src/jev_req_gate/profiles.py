"""问题库(profile)与阈值定义，以及自定义加载。

对应《docs/methodology.md》第三节（MECE 5 面 × 22 原子问题）。
"""
from __future__ import annotations

import json
from typing import Any, Iterable

# 每个问题：key / face / type(score|noul|choice) / instructions / criteria
# noul 的 direction: positive(值高=健康) | negative(值高=有问题)
DEFAULT_PROFILE: list[dict[str, Any]] = [
    # ---- 表述层 Expression ----
    {"key": "clarity", "face": "expression", "type": "score",
     "instructions": "该需求表述的无歧义程度",
     "criteria": ["含混、自相矛盾或无法读懂", "存在明显歧义需解释", "基本清楚但措辞模糊",
                  "清楚，仅有小疑问", "清晰、单义、无歧义"]},
    {"key": "readability", "face": "expression", "type": "score",
     "instructions": "非技术受众能读懂该需求的程度",
     "criteria": ["满口行话、抽象难懂", "偏专业、需背景知识", "基本可懂但需推敲",
                  "较直白", "普通读者可直接理解"]},
    {"key": "atomicity", "face": "expression", "type": "score",
     "instructions": "该需求聚焦单一职责的程度",
     "criteria": ["混杂多条不相关需求", "含两三条相关点", "主体单一带次要信息",
                  "基本单一", "完全单一聚焦"]},

    # ---- 内容层 Content ----
    {"key": "completeness", "face": "content", "type": "score",
     "instructions": "该需求信息完整的程度",
     "criteria": ["关键信息大量缺失", "缺多个要素", "缺少量要素", "基本完整",
                  "完整自足、含边界与异常"]},
    {"key": "self_contained", "face": "content", "type": "noul", "direction": "positive",
     "instructions": "该需求在文档内自足，无需文档外的隐形知识即可正确理解和验证"},
    {"key": "terminology_defined", "face": "content", "type": "noul", "direction": "positive",
     "instructions": "该需求使用的关键术语在本文档内已有明确定义"},
    {"key": "acceptance_quantifiable", "face": "content", "type": "noul", "direction": "positive",
     "instructions": "该需求的验收标准是可量化的"},
    {"key": "implementation_free", "face": "content", "type": "noul", "direction": "negative",
     "instructions": "该需求把具体实现方案或实现细节当成了需求本身（需求与方案混淆）"},
    {"key": "missing_info", "face": "content", "type": "choice",
     "instructions": "该需求缺失哪一类关键信息",
     "criteria": {"prerequisite": "前置条件", "dependency": "依赖接口",
                  "boundary": "边界与异常", "terminology": "术语定义",
                  "acceptance": "验收判据", "none": "无缺失"}},

    # ---- 现实层 Reality（AI 最易翻车，全 positive）----
    {"key": "correct", "face": "reality", "type": "noul", "direction": "positive",
     "instructions": "该需求与业务目标/真实意图一致，是正确的需求"},
    {"key": "feasible", "face": "reality", "type": "noul", "direction": "positive",
     "instructions": "该需求在当前技术/资源约束下可实现"},
    {"key": "necessary", "face": "reality", "type": "noul", "direction": "positive",
     "instructions": "该需求是本次交付实际需要的内容，而非冗余或装饰"},
    {"key": "traceable", "face": "reality", "type": "noul", "direction": "positive",
     "instructions": "该需求可追溯到明确来源（用户诉求/业务目标/上游需求）"},
    {"key": "fidelity", "face": "reality", "type": "noul", "direction": "positive",
     "instructions": "该需求忠实于原始输入意图，未被 AI 扩写发散或跑题"},

    # ---- 关系层 Relation ----
    {"key": "consistent_internal", "face": "relation", "type": "noul", "direction": "positive",
     "instructions": "该条目内部（标题/描述/验收标准）自洽、不矛盾"},
    {"key": "contradicts_siblings", "face": "relation", "type": "noul", "direction": "negative",
     "instructions": "该条与文档中其他条目存在矛盾"},
    {"key": "non_redundant", "face": "relation", "type": "noul", "direction": "positive",
     "instructions": "该条不与已有需求重复"},
    {"key": "dependencies_declared", "face": "relation", "type": "noul", "direction": "positive",
     "instructions": "该条的前置条件/依赖已被显式声明"},

    # ---- 治理层 Governance ----
    {"key": "conforms_template", "face": "governance", "type": "noul", "direction": "positive",
     "instructions": "该条符合团队需求模板/必填字段要求"},
    {"key": "req_type", "face": "governance", "type": "choice",
     "instructions": "该需求属于哪种类型",
     "criteria": {"feature": "功能需求", "nfr": "非功能需求(性能/安全/可用性)",
                  "constraint": "约束(技术/法规/环境)", "assumption": "假设(未经验证的先验)"}},
    {"key": "priority", "face": "governance", "type": "choice",
     "instructions": "该需求的优先级档位",
     "criteria": {"must": "必须", "should": "应该", "could": "可以", "wont": "暂缓"}},
    {"key": "risk", "face": "governance", "type": "choice",
     "instructions": "该需求的风险等级",
     "criteria": {"high": "高风险", "mid": "中风险", "low": "低风险"}},
]

# 参与质量均分的 Score 维度（表述层 + 内容层 completeness）
CORE_SCORES: list[str] = ["clarity", "readability", "atomicity", "completeness"]

# ---- 人话映射层（v0.6.1）：把内部信号名翻译成需求作者能看懂的中文缺陷描述 ----
HUMAN_SHORT: dict[str, str] = {
    "self_contained": "自足性", "correct": "正确性", "feasible": "可行性",
    "necessary": "必要性", "contradicts_siblings": "矛盾", "implementation_free": "方案混入",
    "acceptance_quantifiable": "验收可量化", "non_redundant": "非冗余",
    "terminology_defined": "术语定义", "conforms_template": "模板合规",
    "dependencies_declared": "依赖声明", "traceable": "可追溯", "fidelity": "意图保真",
    "clarity": "无歧义", "atomicity": "原子性", "readability": "可读性",
    "completeness": "完整性", "risk": "风险", "quality": "质量",
}
HUMAN_NOTE: dict[str, str] = {
    "self_contained": "依赖文档外的隐形知识/假设，无法独立理解验证",
    "correct": "与业务/真实意图不一致（可能是 AI 按通用知识编的）",
    "feasible": "当前技术/资源约束下不可行",
    "necessary": "非本次交付实际所需（冗余/装饰）",
    "contradicts_siblings": "与文档中其他条目存在矛盾",
    "implementation_free": "把实现方案/细节当成了需求",
    "acceptance_quantifiable": "验收标准无法量化，不可测试",
    "non_redundant": "与已有需求重复",
    "terminology_defined": "关键术语在文档内无定义",
    "conforms_template": "不符合团队需求模板/缺必填字段",
    "dependencies_declared": "前置条件/依赖未显式声明",
    "traceable": "无法追溯到用户诉求/业务目标来源",
    "fidelity": "偏离原始输入意图（AI 扩写发散）",
    "clarity": "表述含混/有歧义",
    "atomicity": "混杂多条职责",
    "readability": "技术行话过多，非技术读者难懂",
    "completeness": "信息不完整",
}


def human_short(key: str) -> str:
    return HUMAN_SHORT.get(key, key)


def human_note(key: str) -> str:
    return HUMAN_NOTE.get(key, "")

# 已按真实 Jev 输出分布校准（见 docs/methodology.md §5.5）：
#   - 打回只看最可靠信号：现实层白名单 + 跨条目矛盾（负向白名单见 block_neg_keys）
#   - 质量分 Jev 打得保守，仅作提示；terminology_defined / risk 亦仅提示
#   - v0.5.0：implementation_free 从打回移出（实测它对"细节型好需求"系统性误伤，
#     0.7+ 只作黄提示），负向打回仅保留 contradicts_siblings
#   - v0.6.0：绿=关键信号全健康（7 项），黄=有强警告；术语低/个别置信度低/risk=high
#     是 Jev 中文输出常态噪声，只作提示不再把好需求拉进黄
DEFAULT_THRESHOLDS: dict[str, Any] = {
    "block_score": 1.0,
    "review_score": 2.2,
    "block_noul_neg": 0.7,
    "block_noul_pos": 0.3,
    "block_pos_keys": ["self_contained", "correct", "feasible", "necessary"],
    "block_neg_keys": ["contradicts_siblings"],
    "green_score": 2.0,
    "green_noul_min": 0.6,
    "green_self_contained": 0.5,
    "green_contradicts_max": 0.4,
    "green_impl_max": 0.6,
    "green_keys": ["correct", "feasible", "necessary", "acceptance_quantifiable",
                   "non_redundant"],
    "review_pos_weak": 0.5,
    "review_neg_hi": 0.5,
    "noul_mid_low": 0.25,
    "noul_mid_high": 0.75,
    "low_confidence": 0.6,
}


def _load_json_object(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} 必须是 JSON 对象")
    return data


def load_profile(path: str) -> list[dict[str, Any]]:
    """从 JSON 加载自定义问题库。

    格式：{"questions": [...]}，每个元素结构与 DEFAULT_PROFILE 中的问题一致。
    """
    data = _load_json_object(path)
    questions = data.get("questions", data)
    if not isinstance(questions, list) or not questions:
        raise ValueError(f"{path} 缺少非空的 questions 列表")
    return questions


def load_thresholds(path: str) -> dict[str, Any]:
    """从 JSON 加载自定义阈值，返回与默认阈值合并后的结果。"""
    data = _load_json_object(path)
    merged = dict(DEFAULT_THRESHOLDS)
    merged.update(data)
    return merged


def validate_profile(profile: Iterable[dict[str, Any]]) -> list[str]:
    """校验 profile：返回发现的错误列表（空=通过）。"""
    errors: list[str] = []
    keys: list[str] = []
    for q in profile:
        key = q.get("key")
        if key in keys:
            errors.append(f"重复的 key: {key}")
        keys.append(key)
        if q.get("type") not in ("score", "noul", "choice"):
            errors.append(f"{key}: 非法 type={q.get('type')}")
        if q.get("type") == "noul" and q.get("direction") not in ("positive", "negative"):
            errors.append(f"{key}: noul 缺少 direction")
    return errors
