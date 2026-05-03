# notion_codegen/parser.py
"""
页面解析器。

职责：
    将 NotionPage 的块结构解析为 FileOperation 列表。

解析规则：
    识别规则——每个文件条目由两部分组成：
      1. H3 标题块（type="heading_3"），标题文本格式为：  `路径` | 操作类型
      2. 紧随 H3 带的代码块（type="code"），包含文件内容
    如果操作类型是 delete，则不需要代码块。

    四种操作类型（大小写不敏感）：
      - create           创建新文件，若文件已存在则跳过
      - modify:replace   整体替换现有文件
      - modify:patch     精准打 patch，使用 <<<OLD/====/>>>NEW 格式
      - delete           删除文件

    容错设计：
      - 不符合格式的 H3 标题一律忽略，不报错
      - 前缀不是 📁 的子页面不进入递归解析
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Optional

from rich.console import Console

from .log import get_logger
from .notion_reader import NotionPage

console = Console()
logger = get_logger("parser")


# ── 数据结构 ─────────────────────────────────────────────────

class OpType(Enum):
    """\u6587件操作类型。值与 Notion 页面格式规范中的操作类型字符串对应。"""
    CREATE  = "create"
    REPLACE = "modify:replace"
    PATCH   = "modify:patch"
    DELETE  = "delete"


# 操作类型字符串 → OpType 的映射（大小写均可匹配）
_OP_MAP: dict[str, OpType] = {
    "create":         OpType.CREATE,
    "modify:replace": OpType.REPLACE,
    "modify:patch":   OpType.PATCH,
    "delete":         OpType.DELETE,
}


@dataclass
class FileOperation:
    """
    一个待执行的文件操作。

    Attributes:
        file_path:      完整本地路径（= output_dir / 页面中的相对路径）
        op_type:        操作类型
        content:        create/replace 时为文件内容；
                        patch 时为 patch 文本；
                        delete 时为 None
        source_page_id: 来源页面 ID（用于状态追踪）
        source_heading: 原始 H3 标题的纯文本（调试 / 日志用）
    """
    file_path: Path
    op_type: OpType
    content: Optional[str]
    source_page_id: str
    source_heading: str

    def __repr__(self) -> str:
        return (
            f"FileOperation({self.op_type.value}, "
            f"{self.file_path}, "
            f"content={'<none>' if self.content is None else f'{len(self.content)}chars'})"
        )


# ── 解析器 ─────────────────────────────────────────────────

class PageParser:
    """
    将 NotionPage 对象解析为 FileOperation 列表。

    使用方式：
        parser = PageParser()
        ops = parser.parse(page, output_dir=Path("D:/Projects/my-app"))
        for op in ops:
            print(op)
    """

    # 匹配 H3 标题中的文件条目： `路径` | 操作类型
    # 捐获组 1：文件路径，捐获组 2：操作类型
    _HEADING_RE = re.compile(
        r"`([^`]+)`"      # 匹配反引号内的路径
        r"\s*\|\s*"       # 分隔符 |
        r"([\w:]+)",      # 操作类型（字母/数字/下划线/冒号）
        re.IGNORECASE,
    )

    def parse(
        self,
        page: NotionPage,
        output_dir: Path,
        recursive: bool = True,
    ) -> list[FileOperation]:
        """
        解析一个页面，返回所有 FileOperation。

        Args:
            page:       待解析的 NotionPage。
            output_dir: 本地输出根目录，文件路径将拼接在其后。
            recursive:  是否递归解析子页面。
                        True（默认）：递归处理所有 📁 子页面（适合单次调用）。
                        False：只解析当前页面，不递归（由调用方控制递归，避免重复）。

        Returns:
            FileOperation 列表，顺序与页面中出现的顺序一致。
        """
        ops: list[FileOperation] = []
        self._parse_page(page, output_dir, ops, recursive=recursive)
        return ops

    # ── 私有方法 ──────────────────────────────────────────

    def _parse_page(
        self,
        page: NotionPage,
        output_dir: Path,
        ops: list[FileOperation],
        recursive: bool = True,
    ) -> None:
        """解析单个页面的块列表，结果 append 到 ops。"""
        blocks = page.blocks
        i = 0
        while i < len(blocks):
            block = blocks[i]

            if block.get("type") == "heading_3":
                heading_text = self._extract_heading_text(
                    block["heading_3"]["rich_text"]
                )
                op = self._parse_heading(heading_text, output_dir, page.page_id)

                if op is not None:
                    # delete 不需要代码块
                    if op.op_type == OpType.DELETE:
                        ops.append(op)
                    # 其他操作查找紧随其后的代码块
                    elif i + 1 < len(blocks) and blocks[i + 1].get("type") == "code":
                        i += 1
                        op.content = self._extract_code(blocks[i])
                        ops.append(op)
                    else:
                        # H3 后没有代码块：记录警告但不中断流程
                        console.print(
                            f"[yellow]⚠  跳过 '{heading_text}'："
                            f"H3 后未找到代码块[/yellow]"
                        )

            i += 1

        # 递归解析子页面（只在 recursive=True 时执行）
        if recursive:
            for subpage in page.subpages:
                self._parse_page(subpage, output_dir, ops, recursive=True)

    def _parse_heading(
        self,
        text: str,
        output_dir: Path,
        page_id: str,
    ) -> Optional[FileOperation]:
        """
        解析一个 H3 标题文本为 FileOperation。

        成功返回 FileOperation（content 小时 None，由调用方填充）。
        不符合格式时返回 None，调用方忽略。
        """
        m = self._HEADING_RE.search(text.strip())
        if m is None:
            return None

        raw_path = m.group(1).strip()
        raw_op   = m.group(2).strip().lower()

        op_type = _OP_MAP.get(raw_op)
        if op_type is None:
            logger.debug("未知操作类型 '%s'，忽略：%r", raw_op, text)
            console.print(
                f"[yellow]⚠  未知操作类型 '{raw_op}'，忽略：{text!r}[/yellow]"
            )
            return None

        # 将 Notion 页面中的正斜杠路径转换为 Path 对象
        # Path() 在 Windows 上会自动处理正斜杠，无需手动替换
        relative_path = Path(raw_path)
        file_path = (output_dir / relative_path).resolve()

        return FileOperation(
            file_path=file_path,
            op_type=op_type,
            content=None,
            source_page_id=page_id,
            source_heading=text,
        )

    @staticmethod
    def _extract_heading_text(rich_text: list[dict]) -> str:
        """
        提取 H3 标题文本，对 code 标注的片段补回反引号。

        Notion API 中行内代码（`路径`）会被存储为
        annotations.code=True 的片段，plain_text 里不含反引号。
        正则需要反引号来识别路径，因此这里手动补回。
        """
        parts = []
        for seg in rich_text:
            text = seg.get("plain_text", "")
            if seg.get("annotations", {}).get("code"):
                parts.append(f"`{text}`")
            else:
                parts.append(text)
        return "".join(parts)

    @staticmethod
    def _extract_rich_text(rich_text: list[dict]) -> str:
        """
        拼接 Notion rich_text 数组中所有段的 plain_text。

        Notion 中带样式的标题或段落会将文本拆分为多个 rich_text
        对象，每个对象包含一个 plain_text 字段。
        """
        return "".join(
            seg.get("plain_text", "") for seg in rich_text
        )

    @staticmethod
    def _extract_code(code_block: dict) -> str:
        """
        提取代码块的纯文本内容。

        Notion 代码块的内容存储在 block["code"]["rich_text"] 中，
        和普通文本块结构相同。大多数情况下只有一个元素。
        """
        rich_text: list[dict] = code_block.get("code", {}).get("rich_text", [])
        return "".join(seg.get("plain_text", "") for seg in rich_text)