# notion_codegen/notion_reader.py
"""
Notion 页面读取模块。

职责：
  - 根据页面 ID 递归读取主页面和所有 📁 子页面的原始块结构
  - 快速获取页面及子页面的 last_edited_time（不拉内容，用于增量同步检测）

设计原则：
  - 直接操作 Notion API 返回的原始块 dict，不做额外转换
  - 自动处理分页游标（page_size=100）
  - 子页面识别规则：child_page 块的标题以 📁 开头
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Iterator

from notion_client import Client
from notion_client.errors import APIResponseError
from rich.console import Console

from .log import get_logger

console = Console()
logger = get_logger("notion_reader")


# ── 数据结构 ─────────────────────────────────────────────────────

@dataclass
class NotionPage:
    """
    一个 Notion 页面的完整快照。

    Attributes:
        page_id:          页面 ID（32 位不带连字符）
        title:            页面标题的纯文本
        last_edited_time: ISO-8601 时间字符串，Notion 返回的原始值
        blocks:           页面内所有块的平坚列表（不包含子页面的块）
        subpages:         标题以 📁 开头的子页面列表（递归加载）
    """
    page_id: str
    title: str
    last_edited_time: str
    blocks: list[dict]
    subpages: list["NotionPage"] = field(default_factory=list)

    def __repr__(self) -> str:
        return (
            f"NotionPage(id={self.page_id[:8]}..., "
            f"title={self.title!r}, "
            f"blocks={len(self.blocks)}, "
            f"subpages={len(self.subpages)})"
        )

    def iter_all_pages(self) -> Iterator["NotionPage"]:
        """DFS 递归遍历自身和所有子页面，逐个 yield。"""
        yield self
        for sub in self.subpages:
            yield from sub.iter_all_pages()


# ── 读取器 ─────────────────────────────────────────────────────

class NotionReader:
    """
    封装 Notion API 的页面读取器。

    使用方式：
        reader = NotionReader(token="secret_xxx")
        page = reader.read_page("<page_id>")
        for p in page.iter_all_pages():
            print(p.title, len(p.blocks))
    """

    # 子页面标题必须以该 emoji 开头才会被视为目录子页面
    SUBPAGE_PREFIX = "📁"

    def __init__(self, token: str, max_workers: int = 4) -> None:
        """
        Args:
            token:       Notion Integration Token（就是 .env 中的 NOTION_TOKEN）
            max_workers: 并发读取子页面的线程数（默认 4，对 Notion API 速率友好）。
        """
        if not token:
            raise ValueError("Notion token 不能为空，请检查 .env 中的 NOTION_TOKEN。")
        self.client = Client(auth=token)
        self.max_workers = max_workers

    # ── 公共方法 ──────────────────────────────────────────

    def read_page(self, page_id: str, recursive: bool = True) -> NotionPage:
        """
        读取一个页面的完整内容。

        Args:
            page_id:   Notion 页面 ID，32 位不带连字符或带连字符均可。
            recursive: 是否递归读取以 📁 开头的子页面。

        Returns:
            NotionPage 实例。

        Raises:
            APIResponseError: Notion API 返回错误（如页面不存在、无权限等）。
        """
        page_id = self._normalize_id(page_id)

        # 获取页面元数据（标题、last_edited_time 等）
        meta = self._retrieve_page(page_id)
        title = self._extract_title(meta)
        last_edited = meta["last_edited_time"]

        # 拉取页面所有块
        blocks = self._list_all_blocks(page_id)

        # 递归读取子页面
        subpages: list[NotionPage] = []
        if recursive:
            subpage_tasks: list[tuple[str, str]] = []  # (child_id, child_title)
            for block in blocks:
                if self._is_dir_subpage(block):
                    child_id = block["id"].replace("-", "")
                    child_title = block["child_page"]["title"]
                    subpage_tasks.append((child_id, child_title))

            if len(subpage_tasks) >= 2:
                # 并发读取多个子页面
                subpages = self._read_subpages_parallel(subpage_tasks)
            else:
                # 只有 0-1 个子页面，串行即可
                for child_id, child_title in subpage_tasks:
                    console.print(f"  [dim]└─ 📁 {child_title}[/dim]")
                    try:
                        child = self.read_page(child_id, recursive=True)
                        subpages.append(child)
                    except APIResponseError as e:
                        logger.warning("读取子页面失败 (%s): %s", child_title, e)
                        console.print(
                            f"  [yellow]⚠  读取子页面失败 ({child_title}): {e}[/yellow]"
                        )

        return NotionPage(
            page_id=page_id,
            title=title,
            last_edited_time=last_edited,
            blocks=blocks,
            subpages=subpages,
        )

    def _read_subpages_parallel(
        self, tasks: list[tuple[str, str]]
    ) -> list[NotionPage]:
        """
        并发读取多个子页面。

        Args:
            tasks: [(child_id, child_title), ...] 列表。

        Returns:
            成功读取的 NotionPage 列表（顺序与 tasks 一致）。
        """
        console.print(
            f"  [dim]└─ 并发读取 {len(tasks)} 个子页面 (workers={self.max_workers})[/dim]"
        )
        results: dict[str, NotionPage | Exception] = {}

        with ThreadPoolExecutor(max_workers=self.max_workers) as pool:
            future_map = {
                pool.submit(self.read_page, cid, True): (cid, ctitle)
                for cid, ctitle in tasks
            }
            for future in as_completed(future_map):
                cid, ctitle = future_map[future]
                try:
                    results[cid] = future.result()
                    console.print(f"    [dim]✓ {ctitle}[/dim]")
                except APIResponseError as e:
                    logger.warning("读取子页面失败 (%s): %s", ctitle, e)
                    console.print(
                        f"    [yellow]⚠  {ctitle}: {e}[/yellow]"
                    )
                    results[cid] = e

        # 按原始顺序收集成功的结果
        subpages: list[NotionPage] = []
        for cid, _ctitle in tasks:
            r = results.get(cid)
            if isinstance(r, NotionPage):
                subpages.append(r)
        return subpages

    def get_last_edited_map(self, page_id: str) -> dict[str, str]:
        """
        快速获取页面及所有子页面的 last_edited_time。

        这个方法不拉取块内容，只读页面元数据和块列表，
        用于增量同步时快速判断哪些页面有变化。

        Args:
            page_id: 主页面 ID。

        Returns:
            { page_id: last_edited_time } 字典，包含主页面和所有子页面。
        """
        page_id = self._normalize_id(page_id)
        result: dict[str, str] = {}
        self._collect_edited_times(page_id, result)
        return result

    # ── 私有方法 ──────────────────────────────────────────

    def _collect_edited_times(
        self, page_id: str, result: dict[str, str]
    ) -> None:
        """DFS 递归收集所有页面的 last_edited_time，不拉块内容。"""
        meta = self._retrieve_page(page_id)
        result[page_id] = meta["last_edited_time"]

        # 只拉块列表（不读内容），找出子页面
        blocks = self._list_all_blocks(page_id)
        for block in blocks:
            if self._is_dir_subpage(block):
                child_id = block["id"].replace("-", "")
                if child_id not in result:  # 防止循环（正常不应出现，保险）
                    self._collect_edited_times(child_id, result)

    def _retrieve_page(self, page_id: str) -> dict:
        """调用 Notion API 获取页面元数据，由调用方负责异常处理。"""
        return self.client.pages.retrieve(page_id=page_id)  # type: ignore[return-value]

    def _list_all_blocks(self, block_id: str) -> list[dict]:
        """
        获取一个块的所有子块，自动处理 Notion API 的分页游标。

        Args:
            block_id: 块或页面的 ID。

        Returns:
            完整的块列表，顺序与 Notion 页面中一致。
        """
        blocks: list[dict] = []
        cursor: str | None = None

        while True:
            kwargs: dict = {"block_id": block_id, "page_size": 100}
            if cursor:
                kwargs["start_cursor"] = cursor

            resp = self.client.blocks.children.list(**kwargs)  # type: ignore[arg-type]
            blocks.extend(resp["results"])

            if not resp.get("has_more", False):
                break
            cursor = resp.get("next_cursor")

        return blocks

    def _is_dir_subpage(self, block: dict) -> bool:
        """
        判断一个块是否是目录子页面（标题以 📁 开头的 child_page）。

        Notion 将子页面表示为 type=="child_page" 的块，
        标题存储在 block["child_page"]["title"] 中。
        """
        if block.get("type") != "child_page":
            return False
        child_title: str = block.get("child_page", {}).get("title", "")
        return child_title.startswith(self.SUBPAGE_PREFIX)

    def _extract_title(self, page_meta: dict) -> str:
        """
        从页面元数据中提取纯文本标题。

        Notion 页面的标题存储在 properties.title 或 properties.Name 中，
        表现为 rich_text 数组，需要拼接所有段的 plain_text。
        """
        props: dict = page_meta.get("properties", {})
        # 普通页面用 "title"，数据库页面可能用 "Name" 或其他名称
        title_prop: dict = (
            props.get("title")
            or props.get("Name")
            or next(
                (v for v in props.values() if isinstance(v, dict) and v.get("type") == "title"),
                {}
            )
        )
        rich_texts: list = title_prop.get("title", [])
        return "".join(segment.get("plain_text", "") for segment in rich_texts)

    @staticmethod
    def _normalize_id(page_id: str) -> str:
        """统一 ID 格式：去除连字符和首尾空格。"""
        return page_id.strip().replace("-", "")