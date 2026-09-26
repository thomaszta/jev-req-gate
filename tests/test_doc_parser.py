"""doc_parser 文档拆解：编号/列表/表格/续行/上下文分离。"""
from __future__ import annotations

import json

from jev_req_gate.doc_parser import split, write_prepared


class TestNumberedItems:
    def test_decimal_numbers(self):
        doc = "# 需求\n1. 支付网关结算失败时自动重试，最多 3 次\n2.1 库存扣减必须在事务内完成\n3. 提升用户体验"
        p = split(doc)
        assert [it["id"] for it in p["items"]] == ["R01", "R02", "R03"]
        assert [it["source_ref"] for it in p["items"]] == ["1", "2.1", "3"]
        assert "提升用户体验" in p["items"][2]["text"]

    def test_alpha_numbers(self):
        doc = "R01: 支持跨境订单\nREQ-02 阻止删除被引用商品\nFR-3 允许强制删除被引用商品"
        p = split(doc)
        assert [it["source_ref"] for it in p["items"]] == ["R01", "REQ-02", "FR-3"]
        assert [it["id"] for it in p["items"]] == ["R01", "R02", "R03"]


class TestListsAndTables:
    def test_markdown_list(self):
        doc = "- [ ] 支付网关重试 3 次\n- 记录失败日志\n* 回滚事务"
        p = split(doc)
        assert len(p["items"]) == 3
        assert "支付网关重试 3 次" in p["items"][0]["text"]

    def test_table_rows_become_items(self):
        doc = "| 编号 | 需求 |\n| --- | --- |\n| R1 | 重试 3 次 |\n| R2 | 事务回滚 |"
        p = split(doc)
        assert len(p["items"]) == 2
        assert all("R1" in it["text"] or "R2" in it["text"] for it in p["items"])


class TestContinuationAndContext:
    def test_continuation_lines_merge(self):
        doc = "1. 支付网关结算失败时自动重试\n    最多重试 3 次，每次间隔 30 秒\n    并记录失败日志"
        p = split(doc)
        assert len(p["items"]) == 1
        assert "30 秒" in p["items"][0]["text"] and "失败日志" in p["items"][0]["text"]

    def test_background_paragraphs_stay_out_of_items(self):
        doc = "平台含商品、订单、库存三域，技术栈 Python/PostgreSQL。\n\n## 需求\n1. 支付网关重试"
        p = split(doc)
        assert len(p["items"]) == 1
        assert "Python" in p["context_text"]
        assert "Python" not in p["items"][0]["text"]

    def test_document_is_item_level_not_line_fragments(self):
        doc = "## 需求\n1. 支付网关结算失败时自动重试，最多重试 3 次，每次间隔 30 秒，并记录失败日志供排查\n2. 支持跨境订单的创建与查询"
        p = split(doc)
        # document 每条是完整条目文本（含全部细节），不是按行碎片
        assert any("30 秒" in d and "失败日志" in d for d in p["document"])
        assert any("跨境订单" in d for d in p["document"])


class TestStoryAndTableNoise:
    def test_story_title_line_starts_new_item(self):
        """用户故事目标行开新条目，不再被并进上一条验收文本（实测缺陷修复）。"""
        doc = ("## 验收\n"
               "| 编号 | 验收标准 |\n| --- | --- |\n"
               "| AC-1 | 创建订单后状态为待支付 |\n"
               "故事 2：远程下发配方\n"
               "作为一名店长，我可以远程下发配方到咖啡机")
        p = split(doc)
        # AC-1 是条目；"故事 2：远程下发配方" 单独成条目，不再吞进 AC-1
        texts = [it["text"] for it in p["items"]]
        assert any("AC-1" in t for t in texts)
        assert any("远程下发配方" in t for t in texts)
        ac = next(t for t in texts if "AC-1" in t)
        assert "远程下发配方" not in ac  # 未被吞并

    def test_story_us_number_form(self):
        doc = "US-3 取消订单\n作为一名用户，我可以取消未发货订单"
        p = split(doc)
        assert any("取消订单" in it["text"] for it in p["items"])

    def test_table_noise_cells_not_items(self):
        """表格里的"略"/"-"等占位行不产生条目（实测 R24"略"噪声修复）。"""
        doc = ("| 编号 | 验收标准 |\n| --- | --- |\n"
               "| AC-1 | 订单状态变为待支付 |\n| AC-2 | 略 |\n| AC-3 | - |")
        p = split(doc)
        assert len(p["items"]) == 1  # 只有 AC-1
        assert "略" not in " ".join(it["text"] for it in p["items"])


class TestEdgeCases:
    def test_empty_or_decorative_document(self):
        p = split("# 空文档\n\n\n")
        assert p["items"] == []

    def test_clean_strips_markdown_emphasis(self):
        doc = "1. **提升用户体验**，让`首页`加载更快"
        p = split(doc)
        assert "**" not in p["items"][0]["text"]
        assert "首页" in p["items"][0]["text"]

    def test_write_prepared_roundtrip(self, tmp_path):
        doc = "背景：电商平台。\n1. 支付网关重试\nR02: 事务回滚"
        p = split(doc)
        path = write_prepared(str(tmp_path / "reqs.prepared.json"), p)
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert len(data["items"]) == 2
        assert data["items"][0]["id"] == "R01" and data["items"][1]["source_ref"] == "R02"
        assert data["context_text"] and data["document"]
