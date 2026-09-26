"""输入解析与报告导出的测试。"""
import json

from jev_req_gate import cli
from jev_req_gate.report import export_csv, export_json
from jev_req_gate.core import demo_answers


def test_load_text_list_json(tmp_path):
    p = tmp_path / "list.json"
    p.write_text(json.dumps(["a", "b"]), encoding="utf-8")
    assert cli._load_text_list(str(p)) == ["a", "b"]


def test_load_text_list_txt(tmp_path):
    p = tmp_path / "list.txt"
    p.write_text("# comment\n\nline1\nline2\n", encoding="utf-8")
    assert cli._load_text_list(str(p)) == ["line1", "line2"]


def test_load_requirements_json_objects(tmp_path):
    p = tmp_path / "reqs.json"
    p.write_text(json.dumps([{"text": "a"}, {"text": "b", "archived": "old"}]), encoding="utf-8")
    items = cli._load_requirements(str(p))
    assert items == [("a", None), ("b", "old")]


def test_load_requirements_json_strings(tmp_path):
    p = tmp_path / "reqs.json"
    p.write_text(json.dumps(["x", "y"]), encoding="utf-8")
    assert cli._load_requirements(str(p)) == [("x", None), ("y", None)]


def test_export_csv_roundtrip(tmp_path):
    res = [{"id": "R01", "text": "t", "verdict": "green", "q_avg": 4.2, "risk": "low",
            "reasons": [], "answers": demo_answers("good")}]
    out = tmp_path / "r.csv"
    export_csv(str(out), res)
    lines = out.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("id,text,verdict,q_avg,risk,reasons")


def test_export_json_roundtrip(tmp_path):
    res = [{"text": "t", "verdict": "red", "q_avg": None, "risk": "high",
            "reasons": ["x"], "answers": {}}]
    out = tmp_path / "r.json"
    export_json(str(out), res)
    assert json.loads(out.read_text(encoding="utf-8"))[0]["verdict"] == "red"


def test_cli_demo_runs(capsys):
    code = cli.main(["--demo", "good"])
    out = capsys.readouterr().out
    assert "GREEN 放行" in out
    assert code == 0


def test_cli_demo_blocked_exit_code(capsys):
    code = cli.main(["--demo", "unrealistic"])
    assert code == 1


def test_cli_no_gate_requires_no_api_key(tmp_path, capsys, monkeypatch):
    """v0.6.1：--no-gate 只拆解，不初始化 TypeSafeClient，无需 API key。"""
    doc = tmp_path / "req.md"
    doc.write_text("# 需求\n\n1. 用户可登录\n2. 用户可登出\n", encoding="utf-8")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    code = cli.main(["--from-document", str(doc), "--no-gate"])
    out = capsys.readouterr().out
    assert code == 0
    assert "拆解完成：2 条需求" in out
    assert "[R01]" in out and "[R02]" in out
    assert (tmp_path / "req.md.prepared.json").exists()
