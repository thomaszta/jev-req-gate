"""decide 路由判定与 demo 归一化的单元测试。"""
import pytest

from jev_req_gate.core import demo_answers, decide
from jev_req_gate.profiles import DEFAULT_PROFILE, DEFAULT_THRESHOLDS


def _decide(case: str):
    return decide(demo_answers(case), DEFAULT_THRESHOLDS, DEFAULT_PROFILE)


def test_good_green():
    verdict, reasons, detail = _decide("good")
    assert verdict == "green"
    assert reasons == []
    assert detail["q_avg"] is not None


def test_ambiguous_yellow():
    verdict, reasons, _ = _decide("ambiguous")
    assert verdict == "yellow"
    assert any("self_contained" in r for r in reasons)


def test_unrealistic_red():
    verdict, reasons, _ = _decide("unrealistic")
    assert verdict == "red"
    assert any("feasible" in r for r in reasons)


def test_terminology_low_not_red():
    """terminology_defined 低不应触发打回（已降权，仅提示）。"""
    answers = demo_answers("good")
    answers["terminology_defined"] = {"noul": 0.15}
    verdict, _, _ = decide(answers, DEFAULT_THRESHOLDS, DEFAULT_PROFILE)
    assert verdict in ("green", "yellow")
    assert verdict != "red"


def test_contradiction_red():
    """跨条目矛盾是打回硬信号。"""
    answers = demo_answers("good")
    answers["contradicts_siblings"] = {"noul": 0.85}
    verdict, reasons, _ = decide(answers, DEFAULT_THRESHOLDS, DEFAULT_PROFILE)
    assert verdict == "red"
    assert any("contradicts_siblings" in r for r in reasons)


def test_feasible_low_red():
    answers = demo_answers("good")
    answers["feasible"] = {"noul": 0.2}
    verdict, _, _ = decide(answers, DEFAULT_THRESHOLDS, DEFAULT_PROFILE)
    assert verdict == "red"


def test_non_whitelist_positive_low_only_yellow():
    """conforms_template 低不再拉黄（v0.6.0：无团队模板参照时 Jev 给值随意，弱噪声）。

    团队重视模板合规可用 --thresholds-file 把它加回 green_keys。
    """
    answers = demo_answers("good")
    answers["conforms_template"] = {"noul": 0.2}
    verdict, _, _ = decide(answers, DEFAULT_THRESHOLDS, DEFAULT_PROFILE)
    assert verdict == "green"


def test_mid_band_yellow():
    answers = demo_answers("good")
    answers["self_contained"] = {"noul": 0.45}  # < green_self_contained 0.5 → 强警告
    verdict, reasons, _ = decide(answers, DEFAULT_THRESHOLDS, DEFAULT_PROFILE)
    assert verdict == "yellow"
    assert any("不确定" in r for r in reasons)


def test_implementation_free_high_only_yellow():
    """v0.5.0/v0.6.0：implementation_free 不参与红，但 > green_impl_max 0.6 是强警告→黄。

    实测发现它对"细节型好需求"（指标/约束/兼容性）系统性误伤，不应红；
    但"方案混入"明显时也不该绿，留作人工复核。
    """
    answers = demo_answers("good")
    answers["implementation_free"] = {"noul": 0.85}
    verdict, reasons, _ = decide(answers, DEFAULT_THRESHOLDS, DEFAULT_PROFILE)
    assert verdict == "yellow"
    assert any("方案混入" in r for r in reasons)


def test_block_neg_keys_override_restores_red():
    """自定义 block_neg_keys 可把 implementation_free 重新拉回打回（团队需要时）。"""
    t = dict(DEFAULT_THRESHOLDS)
    t["block_neg_keys"] = ["contradicts_siblings", "implementation_free"]
    answers = demo_answers("good")
    answers["implementation_free"] = {"noul": 0.85}
    verdict, reasons, _ = decide(answers, t, DEFAULT_PROFILE)
    assert verdict == "red"
    assert any("implementation_free" in r for r in reasons)


def test_weak_noise_does_not_prevent_green():
    """v0.6.0：术语低 / risk=high / 个别置信度低是 Jev 中文输出常态噪声，不拉黄。

    绿=关键信号全健康；弱噪声只作提示。实测好需求 r01–r05 的关键信号都健康，
    只因这些噪声被拉进黄——本用例锁定该修复。
    """
    answers = demo_answers("good")
    answers["terminology_defined"] = {"noul": 0.15}
    answers["risk"] = {"choice": "high", "confidence": 0.7}
    answers["atomicity"] = {"score": 4.3, "confidence": 0.2}
    verdict, _, _ = decide(answers, DEFAULT_THRESHOLDS, DEFAULT_PROFILE)
    assert verdict == "green"


def test_green_requires_green_keys_healthy():
    answers = demo_answers("good")
    answers["necessary"] = {"noul": 0.5}  # < green_noul_min 0.6 → 强警告
    verdict, reasons, _ = decide(answers, DEFAULT_THRESHOLDS, DEFAULT_PROFILE)
    assert verdict == "yellow"
    assert any("必要性" in r for r in reasons)


def test_demo_cases_valid():
    for case in ("good", "ambiguous", "unrealistic"):
        a = demo_answers(case)
        # 归一化结构必须包含全部 22 个 key
        assert set(a.keys()) == {q["key"] for q in DEFAULT_PROFILE}
