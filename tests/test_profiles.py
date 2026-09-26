"""问题库(profile)完整性与阈值校验。"""
from collections import Counter

from jev_req_gate.profiles import (
    CORE_SCORES,
    DEFAULT_PROFILE,
    DEFAULT_THRESHOLDS,
    validate_profile,
)


def test_total_questions():
    assert len(DEFAULT_PROFILE) == 22


def test_face_distribution():
    counts = Counter(q["face"] for q in DEFAULT_PROFILE)
    assert counts == {"expression": 3, "content": 6, "reality": 5,
                      "relation": 4, "governance": 4}


def test_primitive_distribution():
    counts = Counter(q["type"] for q in DEFAULT_PROFILE)
    assert counts == {"score": 4, "noul": 14, "choice": 4}


def test_no_duplicate_keys():
    keys = [q["key"] for q in DEFAULT_PROFILE]
    assert len(keys) == len(set(keys))


def test_every_question_well_formed():
    for q in DEFAULT_PROFILE:
        assert q["key"]
        assert q["face"] in ("expression", "content", "reality", "relation", "governance")
        assert q["type"] in ("score", "noul", "choice")
        assert q["instructions"]
        if q["type"] == "noul":
            assert q["direction"] in ("positive", "negative")
        if q["type"] == "score":
            assert len(q["criteria"]) >= 2
        if q["type"] == "choice":
            assert isinstance(q["criteria"], dict) and q["criteria"]


def test_core_scores_exist_in_profile():
    profile_keys = {q["key"] for q in DEFAULT_PROFILE}
    assert set(CORE_SCORES) <= profile_keys


def test_default_profile_validates():
    assert validate_profile(DEFAULT_PROFILE) == []


def test_validate_detects_duplicate():
    bad = list(DEFAULT_PROFILE[:1]) * 2
    assert any("重复" in e for e in validate_profile(bad))


def test_thresholds_have_required_keys():
    for k in ("block_score", "review_score", "block_noul_neg", "block_noul_pos",
              "block_pos_keys", "review_pos_weak", "noul_mid_low", "noul_mid_high"):
        assert k in DEFAULT_THRESHOLDS
