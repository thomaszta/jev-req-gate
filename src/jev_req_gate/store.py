"""请求缓存：SQLite 存储每次 Jev 判定，供「判断一次、阈值随便调」与标注校准闭环使用。

同一请求（同一 model + state + 问题库）只调用一次 Jev，之后直接读缓存；
`jev-req-gate export/eval` 基于缓存导出待标注数据并扫描推荐阈值。
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
from typing import Any

DEFAULT_DB = os.environ.get("JEV_REQ_GATE_DB", "~/.jev_req_gate/cache.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS judgments(
    id            INTEGER PRIMARY KEY,
    ts            REAL NOT NULL,
    request_hash  TEXT NOT NULL UNIQUE,
    model         TEXT NOT NULL,
    status        TEXT NOT NULL,
    text          TEXT NOT NULL,
    answers       TEXT,
    error_code    TEXT,
    verdict       TEXT,
    reasons       TEXT
);
CREATE INDEX IF NOT EXISTS judgments_status ON judgments(status);
"""


def request_hash(state: Any, profile: list[dict[str, Any]] | None, model: str) -> str:
    """同一 (state, profile, model) 得到同一哈希；state 与 profile 任一变化都会重新判断。"""
    blob = json.dumps(
        {"model": model, "state": state, "profile": profile},
        ensure_ascii=False, sort_keys=True, default=str,
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


class Store:
    """SQLite 缓存库。只把成功的判定写回；失败不缓存，下次运行自动重试。"""

    def __init__(self, path: str | None = None):
        self.path = os.path.expanduser(str(path or DEFAULT_DB))
        if self.path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        self.db = sqlite3.connect(self.path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript(_SCHEMA)

    def close(self) -> None:
        self.db.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ---- 读写 ----
    def cached(self, h: str) -> dict[str, Any] | None:
        """命中返回 dict（answers/verdict/reasons/model），未命中返回 None。"""
        row = self.db.execute(
            "SELECT model, answers, verdict, reasons FROM judgments "
            "WHERE request_hash=? AND status='ok' ORDER BY id DESC LIMIT 1",
            (h,),
        ).fetchone()
        if row is None:
            return None
        return {
            "model": row["model"],
            "answers": json.loads(row["answers"]),
            "verdict": row["verdict"],
            "reasons": json.loads(row["reasons"] or "[]"),
        }

    def log(self, h: str, model: str, status: str, text: str,
            answers: dict[str, Any] | None = None, error_code: str | None = None,
            verdict: str | None = None, reasons: list[str] | None = None) -> None:
        with self.db:
            self.db.execute(
                """INSERT INTO judgments(ts, request_hash, model, status, text, answers,
                       error_code, verdict, reasons)
                   VALUES(?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(request_hash) DO UPDATE SET
                       ts=excluded.ts, status=excluded.status, text=excluded.text,
                       answers=excluded.answers, error_code=excluded.error_code,
                       verdict=excluded.verdict, reasons=excluded.reasons""",
                (time.time(), h, model, status, text,
                 json.dumps(answers, ensure_ascii=False) if answers is not None else None,
                 error_code, verdict,
                 json.dumps(reasons or [], ensure_ascii=False)),
            )

    # ---- 统计 / 清理 ----
    def stats(self) -> dict[str, Any]:
        row = self.db.execute(
            "SELECT COUNT(*) AS n, SUM(status='ok') AS ok, SUM(status='error') AS err, "
            "MAX(ts) AS last FROM judgments"
        ).fetchone()
        return {
            "rows": row["n"] or 0,
            "ok": row["ok"] or 0,
            "errors": row["err"] or 0,
            "last_ts": row["last"],
        }

    def clear(self) -> int:
        with self.db:
            cur = self.db.execute("DELETE FROM judgments")
        return cur.rowcount

    # ---- export 用：去重后的成功判定 ----
    def ok_rows(self) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT request_hash, ts, model, text, answers, verdict, reasons "
            "FROM judgments WHERE status='ok' ORDER BY ts DESC"
        ).fetchall()
        seen: set[str] = set()
        out: list[dict[str, Any]] = []
        for r in rows:
            if r["request_hash"] in seen:
                continue
            seen.add(r["request_hash"])
            out.append({
                "hash": r["request_hash"],
                "ts": r["ts"],
                "model": r["model"],
                "text": r["text"],
                "answers": json.loads(r["answers"]),
                "verdict": r["verdict"],
                "reasons": json.loads(r["reasons"] or "[]"),
            })
        return out
