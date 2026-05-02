# notion_codegen/config.py
"""
配置加载模块。
优先级（从高到低）：命令行参数 > 环境变量（.env）> .codegen.toml > 默认值
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import toml
from dotenv import load_dotenv

# 加载 .env 文件（若存在）
load_dotenv()


@dataclass
class Config:
    # ── Notion ──────────────────────────────
    notion_token: str     # Notion Integration Token
    page_id: str          # 目标页面 ID
    output_dir: Path      # 本地输出根目录

    # ── LLM ─────────────────────────────────
    llm_provider: str     # provider 名称
    llm_api_key: str      # API Key
    llm_model: str        # 模型名称（空字符串 = 使用 provider 默认值）

    # ── Sync ────────────────────────────────
    state_file: Path      # 状态数据库文件路径
    auto_delete: bool     # 页面消失时是否自动删本地文件

    def validate(self) -> None:
        """校验必填项，缺失时抛出友好错误。"""
        if not self.notion_token:
            raise ValueError(
                "NOTION_TOKEN 未设置。\n"
                "请在 .env 文件中添加：NOTION_TOKEN=secret_xxx\n"
                "获取地址：https://www.notion.so/my-integrations"
            )
        if not self.page_id:
            raise ValueError(
                "未指定 Notion 页面 ID。\n"
                "请通过以下任一方式提供：\n"
                "  1. 命令行参数：--page-id <id>\n"
                "  2. 环境变量：NOTION_PAGE_ID=<id>\n"
                "  3. .codegen.toml 中的 [notion] page_id = \"<id>\""
            )


def load_config(toml_path: str = ".codegen.toml") -> Config:
    """
    加载并合并所有配置来源，返回 Config 实例。

    Args:
        toml_path: .codegen.toml 文件路径，默认在当前工作目录下查找。
    """
    # 读取 .codegen.toml（若存在）
    raw: dict = {}
    p = Path(toml_path)
    if p.exists():
        raw = toml.load(str(p))

    notion_cfg: dict = raw.get("notion", {})
    llm_cfg: dict = raw.get("llm", {})
    sync_cfg: dict = raw.get("sync", {})

    return Config(
        # 环境变量优先于 toml
        notion_token=os.getenv("NOTION_TOKEN", ""),
        page_id=(
            os.getenv("NOTION_PAGE_ID")
            or notion_cfg.get("page_id", "")
        ),
        output_dir=Path(
            os.getenv("OUTPUT_DIR")
            or notion_cfg.get("output_dir", ".")
        ),
        llm_provider=(
            os.getenv("LLM_PROVIDER")
            or llm_cfg.get("provider", "siliconflow")
        ),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_model=(
            os.getenv("LLM_MODEL")
            or llm_cfg.get("model", "")
        ),
        state_file=Path(
            sync_cfg.get("state_file", ".codegen_state.db")
        ),
        auto_delete=sync_cfg.get("auto_delete", False),
    )