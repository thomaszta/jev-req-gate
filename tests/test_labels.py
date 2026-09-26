"""labels.py export/eval 标注校准闭环。"""
from __future__ import annotations

import json

from jev_req_gate.labels import evaluate, export, load
from jev_req_gate.store import Store


def _row(text: str, feasible: float, label: str | None = None,
         verdict: str = "green", other_healthy: bool = True) -> dict:
    a = {
        "clarity": {"score": 4.5, "confidence": 0.9},
        "readability": {"score": 4.2, "confidence": 0.88},
        "atomicity": {"score": 4.3, "confidence": 0.87},
        "completeness": {"score": 4.2, "confidence": 0.85},
        "self_contained": {"noul": 0.9 if other_healthy else 0.5},
        "terminology_defined": {"noul": 0.85},
        "acceptance_quantifiable": {"noul": 0.9},
        "implementation_free": {"noul": 0.1},
        "missing_info": {"choice": "none", "confidence": 0.9},
        "correct": {"noul": 0.92},
        "feasible": {"noul": feasible},
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
    return {"hash": "h-" + text, "text": text, "verdict": verdict,
            "reasons": [], "answers": a, "label": label}


class TestExport:
    def test_export_writes_labelable_jsonl(self, tmp_path):
        with Store(":memory:") as store:
            store.log("h1", "m", "ok", "需求A", _row("需求A", 0.9)["answers"], verdict="green", reasons=[])
            store.log("h2", "m", "ok", "需求B", _row("需求B", 0.2)["answers"], verdict="red", reasons=["x"])
            store.log("h3", "m", "error", "需求C", error_code="timeout")
            out = tmp_path / "segs.jsonl"
            assert export(store, str(out)) == 2
            rows = load(str(out))
            assert len(rows) == 2
            assert {r["label"] for r in rows} == {None}
            assert {r["verdict"] for r in rows} == {"green", "red"}
            assert all("answers" in r and "text" in r for r in rows)


class TestEvaluate:
    def test_recommends_k_with_least_false_under_error_cap(self):
        rows = [
            _row("好需求", 0.9, "pass"),                    # green，人工放行 → 误伤 0
            _row("坏需求A", 0.2, "block"),                  # 恒 red → 拦截
            _row("坏需求B", 0.28, "block"),                 # k≥0.95 变 red，其余 yellow → 恒非 green
            _row("灰色需求", 0.22, "pass"),                 # k≥0.75 变 red → 大 k 误伤
        ]
        report = evaluate(rows, max_error=0.1)
        assert report["labeled"] == 4 and report["n_block"] == 2 and report["n_pass"] == 2
        assert report["unrecoverable"] is False
        # error=0 恒成立；误伤在 k≤0.7 为 0，k≥0.75 为 1/2 → 推荐取误伤最小且更严的 k=0.7
        assert report["recommended_k"] == 0.7
        assert report["recommended_thresholds"]["block_noul_pos"] == round(0.3 * 0.7, 4)
        assert report["agreement"] is not None

    def test_error_above_cap_marks_unrecoverable(self):
        # 健康答案（恒 green）但人工标 block → 任何 k 都漏检
        rows = [
            _row("被放行的坏需求", 0.9, "block"),
            _row("坏需求", 0.2, "block"),
        ]
        report = evaluate(rows, max_error=0.1)
        assert report["recommended_k"] is None
        assert report["unrecoverable"] is True
        assert report["sweep"][0]["error"] >= 0.5

    def test_no_labeled_rows(self):
        rows = [_row("x", 0.9, None)]
        report = evaluate(rows)
        assert report["labeled"] == 0 and report["recommended_k"] is None

    def test_sweep_covers_range(self):
        rows = [_row("好", 0.9, "pass")]
        report = evaluate(rows)
        ks = [s["k"] for s in report["sweep"]]
        assert ks[0] == 0.6 and ks[-1] == 1.4 and len(ks) == 17
