"""store.py 请求缓存与 run_gate 缓存复用。"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from jev_req_gate.core import build_state, run_gate
from jev_req_gate.profiles import DEFAULT_PROFILE
from jev_req_gate.store import Store, request_hash


def _sdk(answers: dict) -> dict:
    """把归一化 answers dict 转成 SDK 风格对象（normalize_sdk_response 的输入）。"""
    out = {}
    for k, v in answers.items():
        if "noul" in v:
            out[k] = SimpleNamespace(type="noul", noul=v["noul"])
        elif "choice" in v:
            out[k] = SimpleNamespace(type="choice", choice=v["choice"],
                                     confidence=v.get("confidence"),
                                     probabilities=v.get("probabilities"))
        else:
            out[k] = SimpleNamespace(type="score", score=v["score"],
                                     confidence=v.get("confidence"), legend=None)
    return out


class FakeClient:
    def __init__(self, response, explode: bool = False):
        self.response = response
        self.calls = 0
        self.explode = explode

    def system_one(self, **kw):
        self.calls += 1
        if self.explode:
            raise RuntimeError("不应再次调用 Jev（缓存应命中）")
        return self.response


GOOD = {
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
BAD = dict(GOOD, feasible={"noul": 0.2})


class TestStore:
    def test_write_and_hit(self):
        with Store(":memory:") as store:
            h = "abc"
            assert store.cached(h) is None
            store.log(h, "jev-latest", "ok", "需求", GOOD, verdict="green", reasons=[])
            hit = store.cached(h)
            assert hit is not None and hit["verdict"] == "green"
            assert hit["answers"]["feasible"]["noul"] == 0.9

    def test_failed_judgment_is_not_cached(self):
        with Store(":memory:") as store:
            store.log("e1", "jev-latest", "error", "需求", error_code="timeout")
            assert store.cached("e1") is None  # 失败不缓存，下次自动重试

    def test_ok_rows_dedup_by_hash(self):
        with Store(":memory:") as store:
            store.log("h1", "m", "ok", "a", GOOD, verdict="green", reasons=[])
            store.log("h1", "m", "ok", "a2", GOOD, verdict="green", reasons=[])  # 同 hash 更新
            store.log("h2", "m", "ok", "b", BAD, verdict="red", reasons=["x"])
            store.log("h3", "m", "error", "c", error_code="timeout")
            rows = store.ok_rows()
            assert len(rows) == 2
            assert {r["verdict"] for r in rows} == {"green", "red"}

    def test_stats_and_clear(self):
        with Store(":memory:") as store:
            store.log("h1", "m", "ok", "a", GOOD)
            store.log("h2", "m", "error", "b", error_code="x")
            s = store.stats()
            assert (s["rows"], s["ok"], s["errors"]) == (2, 1, 1)
            assert store.clear() == 2
            assert store.stats()["rows"] == 0


class TestRequestHash:
    def test_stable_and_sensitive(self):
        state = build_state("需求", project_context="ctx", existing=["a", "b"])
        h1 = request_hash(state, DEFAULT_PROFILE, "jev-latest")
        h2 = request_hash(state, DEFAULT_PROFILE, "jev-latest")
        assert h1 == h2
        assert request_hash(build_state("别的需求"), DEFAULT_PROFILE, "jev-latest") != h1
        assert request_hash(state, [], "jev-latest") != h1  # 问题库变化也重新判断


class TestRunGateCache:
    def test_second_run_reuses_without_calling_api(self):
        with Store(":memory:") as store:
            client = FakeClient(SimpleNamespace(model="jev-1.13.0", answers=_sdk(GOOD)))
            r1 = run_gate("需求", {"project_context": "ctx"}, client=client, store=store)
            assert r1["verdict"] == "green" and r1["cached"] is False
            assert client.calls == 1

            # 第二次：client 若被调用会抛异常 → 证明走了缓存
            explode = FakeClient(None, explode=True)
            r2 = run_gate("需求", {"project_context": "ctx"}, client=explode, store=store)
            assert r2["verdict"] == "green" and r2["cached"] is True
            assert explode.calls == 0

    def test_different_text_is_not_cached(self):
        with Store(":memory:") as store:
            client = FakeClient(SimpleNamespace(model="jev-1.13.0", answers=_sdk(GOOD)))
            run_gate("需求A", client=client, store=store)
            run_gate("需求B", client=client, store=store)
            assert client.calls == 2  # 文本不同 → 两次真实调用

    def test_context_changes_hash(self):
        with Store(":memory:") as store:
            client = FakeClient(SimpleNamespace(model="jev-1.13.0", answers=_sdk(GOOD)))
            run_gate("需求", {"project_context": "ctx1"}, client=client, store=store)
            run_gate("需求", {"project_context": "ctx2"}, client=client, store=store)
            assert client.calls == 2
