# notion_codegen/state.py
"""
SQLite 状态追踪模块。

职责：
    记录每个已同步过的 Notion 页面的 last_edited_time，
    在下次运行时用于判断是否需要重新同步该页面。

数据库文件位置：
    默认存放在项目根目录的 .codegen_state.db，
    也可通过构造函数参数自定义路径。

表结构（pages）：
    page_id         TEXT PRIMARY KEY  — Notion 页面 ID
    last_edited_at  TEXT NOT NULL     — 上次同步时的 last_edited_time (ISO-8601)
    synced_at       TEXT NOT NULL     — 本机执行同步的时间 (ISO-8601 UTC)
"""
from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS pages (
    page_id         TEXT PRIMARY KEY,
    last_edited_at  TEXT NOT NULL,
    synced_at       TEXT NOT NULL
);
"""


class StateDB:
    """
    Notion 页面同步状态的持久化存储。

    使用方式：
        db = StateDB()                          # 默认路径
        db = StateDB(Path(".codegen_state.db")) # 自定义路径

        if db.needs_sync(page_id, current_last_edited_at):
            # 执行同步 ...
            db.mark_synced(page_id, current_last_edited_at)
    """

    def __init__(self, db_path: Path = Path(".codegen_state.db")) -> None:
        self.db_path = db_path
        self._conn   = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(_CREATE_TABLE_SQL)
        self._conn.commit()

    # ── 核心 API ──────────────────────────────────────────────

    def needs_sync(self, page_id: str, current_last_edited_at: str) -> bool:
        """
        判断页面是否需要重新同步。

        如果页面从未同步过，或者 Notion 上的 last_edited_time
        比上次记录的更新，则返回 True。

        Args:
            page_id:                Notion 页面 ID。
            current_last_edited_at: Notion API 返回的最新编辑时间（ISO-8601 字符串）。

        Returns:
            True  → 需要同步
            False → 无需同步（未发生变化）
        """
        row = self._conn.execute(
            "SELECT last_edited_at FROM pages WHERE page_id = ?",
            (page_id,),
        ).fetchone()

        if row is None:
            return True  # 从未同步过

        # 比较 ISO-8601 字符串（Notion 时间戳格式固定，直接字符串比较可靠）
        return current_last_edited_at > row["last_edited_at"]

    def mark_synced(
        self,
        page_id: str,
        last_edited_at: str,
    ) -> None:
        """
        将页面标记为已同步，记录本次同步时的 last_edited_time。

        Args:
            page_id:        Notion 页面 ID。
            last_edited_at: 本次同步时 Notion 页面的 last_edited_time。
        """
        now_utc = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            """
            INSERT INTO pages (page_id, last_edited_at, synced_at)
            VALUES (?, ?, ?)
            ON CONFLICT(page_id) DO UPDATE SET
                last_edited_at = excluded.last_edited_at,
                synced_at      = excluded.synced_at
            """,
            (page_id, last_edited_at, now_utc),
        )
        self._conn.commit()

    def get_record(self, page_id: str) -> dict | None:
        """
        查询某页面的同步记录。

        Returns:
            包含 page_id / last_edited_at / synced_at 的字典，
            如果从未同步则返回 None。
        """
        row = self._conn.execute(
            "SELECT * FROM pages WHERE page_id = ?",
            (page_id,),
        ).fetchone()
        return dict(row) if row else None

    def clear(self) -> None:
        """清空所有同步状态（用于强制全量同步）。"""
        self._conn.execute("DELETE FROM pages")
        self._conn.commit()

    def close(self) -> None:
        """关闭数据库连接。"""
        self._conn.close()

    # ── 上下文管理器支持 ──────────────────────────────────────

    def __enter__(self) -> "StateDB":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()