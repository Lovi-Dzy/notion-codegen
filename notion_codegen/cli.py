# notion_codegen/cli.py
"""
CLI 入口。

命令列表：
    sync   从 Notion 页面同步代码到本地
    status 查看某页面的上次同步状态
    reset  清空所有同步状态（下次将全量同步）

典型用法（PowerShell）：
    python -m notion_codegen sync <page_id_or_url>
    python -m notion_codegen sync <page_id_or_url> --output D:\\Projects\\my-app
    python -m notion_codegen sync <page_id_or_url> --dry-run
    python -m notion_codegen sync <page_id_or_url> --force
    python -m notion_codegen status <page_id_or_url>
    python -m notion_codegen reset
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from .config import load_config
from .executor import Executor
from .notion_reader import NotionReader
from .parser import PageParser
from .state import StateDB

console = Console()

# ── 工具函数 ──────────────────────────────────────────────────

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{4}-?[0-9a-f]{12}",
    re.IGNORECASE,
)


def _extract_page_id(page_id_or_url: str) -> str:
    """
    从原始输入中提取 Notion 页面 ID。

    接受以下格式：
      - 纯 UUID（含或不含连字符）
      - Notion 页面 URL（包含末尾的 32 位 hex ID）

    Returns:
        不含连字符的 32 位小写 hex 字符串。
    """
    m = _UUID_RE.search(page_id_or_url)
    if m is None:
        console.print(
            f"[red]错误：无法从输入中识别 Notion 页面 ID：{page_id_or_url!r}[/red]"
        )
        sys.exit(1)
    return m.group(0).replace("-", "")


def _get_token() -> str:
    """从环境变量获取 NOTION_TOKEN，未设置则报错退出。"""
    token = os.getenv("NOTION_TOKEN", "").strip()
    if not token:
        console.print(
            "[red]错误：未设置 NOTION_TOKEN 环境变量。\n"
            "请在项目根目录创建 .env 文件并填写：\n"
            "  NOTION_TOKEN=secret_xxxxxxxxxxxx[/red]"
        )
        sys.exit(1)
    return token


# ── CLI 定义 ──────────────────────────────────────────────────

@click.group()
def cli() -> None:
    """notion-codegen：将 Notion 页面同步为本地代码文件。"""
    load_dotenv()


@cli.command()
@click.argument("page", metavar="PAGE_ID_OR_URL")
@click.option(
    "--output", "-o",
    default=None,
    help="本地输出根目录（覆盖 .codegen.toml 中的 output_dir）。",
)
@click.option(
    "--dry-run", "-n",
    is_flag=True,
    default=False,
    help="只预览操作，不写入磁盘。",
)
@click.option(
    "--force", "-f",
    is_flag=True,
    default=False,
    help="忽略状态缓存，强制全量同步。",
)
@click.option(
    "--fail-fast",
    is_flag=True,
    default=False,
    help="遇到第一个错误立即停止。",
)
def sync(
    page: str,
    output: str | None,
    dry_run: bool,
    force: bool,
    fail_fast: bool,
) -> None:
    """
    从 Notion 页面同步代码到本地。

    PAGE_ID_OR_URL 可以是 Notion 页面 URL 或 32 位 ID。
    """
    # ── 1. 初始化 ──────────────────────────────────────────
    page_id = _extract_page_id(page)
    token   = _get_token()
    cfg     = load_config()

    # 输出目录优先级：CLI --output > .codegen.toml > 当前目录
    if output:
        output_dir = Path(output).resolve()
    elif cfg.output_dir:
        output_dir = Path(cfg.output_dir).resolve()
    else:
        output_dir = Path.cwd()

    db_path = Path(cfg.state_file) if cfg.state_file else Path(".codegen_state.db")

    console.print(
        Panel(
            f"[bold]Notion Codegen[/bold]\n"
            f"页面 ID  : [cyan]{page_id}[/cyan]\n"
            f"输出目录 : [cyan]{output_dir}[/cyan]\n"
            f"Dry-run  : {'[yellow]是[/yellow]' if dry_run else '[green]否[/green]'}\n"
            f"强制同步 : {'[yellow]是[/yellow]' if force else '[green]否[/green]'}",
            title="运行参数",
        )
    )

    # ── 2. 读取 Notion 页面 ───────────────────────────────
    console.print("\n[bold cyan]► 读取 Notion 页面...[/bold cyan]")
    reader = NotionReader(token=token)

    try:
        root_page = reader.read_page(page_id)
    except Exception as exc:  # noqa: BLE001
        console.print(f"[red]读取页面失败：{exc}[/red]")
        sys.exit(1)

    # ── 3. 增量检查 ───────────────────────────────────────
    with StateDB(db_path) as db:
        # 收集所有需要解析的页面（含子页面）
        all_pages = _collect_all_pages(root_page)
        pages_to_parse = []

        for p in all_pages:
            if force or db.needs_sync(p.page_id, p.last_edited_time):
                pages_to_parse.append(p)
            else:
                console.print(
                    f"[dim]⏭  跳过未变更页面：{p.title or p.page_id}[/dim]"
                )

        if not pages_to_parse:
            console.print(
                "\n[green]✅ 所有页面均未变更，无需同步。[/green]"
            )
            return

        console.print(
            f"\n[bold cyan]► 解析文件操作[/bold cyan] "
            f"（{len(pages_to_parse)}/{len(all_pages)} 个页面有变更）"
        )

        # ── 4. 解析 ──────────────────────────────────────
        parser  = PageParser()
        all_ops = []
        for p in pages_to_parse:
            # recursive=False 避免重复解析：cli 已通过 _collect_all_pages 逐一处理子页面
            ops = parser.parse(p, output_dir=output_dir, recursive=False)
            all_ops.extend(ops)

        if not all_ops:
            console.print(
                "[yellow]⚠  解析到 0 个文件操作。\n"
                "   请检查 Notion 页面中是否有格式为 `路径` | 操作 的 H3 标题。[/yellow]"
            )
            # 仍然更新状态，避免下次重复解析
            for p in pages_to_parse:
                if not dry_run:
                    db.mark_synced(p.page_id, p.last_edited_time)
            return

        console.print(f"   共解析到 [bold]{len(all_ops)}[/bold] 个文件操作")

        # ── 5. 执行 ──────────────────────────────────────
        console.print(
            f"\n[bold cyan]► {'预览（Dry-run）' if dry_run else '执行文件操作'}...[/bold cyan]"
        )
        executor = Executor(dry_run=dry_run, fail_fast=fail_fast)
        summary  = executor.execute(all_ops)
        summary.print_summary()

        # ── 6. 更新状态 ──────────────────────────────────
        if not dry_run and not summary.has_failures:
            for p in pages_to_parse:
                db.mark_synced(p.page_id, p.last_edited_time)
            console.print("\n[dim]状态已更新至 SQLite 缓存。[/dim]")
        elif dry_run:
            console.print("\n[dim]Dry-run 模式，状态未更新。[/dim]")
        else:
            console.print(
                "\n[yellow]⚠  存在失败操作，状态未更新（下次运行将重试）。[/yellow]"
            )

    # ── 7. 最终提示 ───────────────────────────────────────
    if summary.has_failures:
        console.print("\n[bold red]同步完成，但存在失败项，请检查上方日志。[/bold red]")
        sys.exit(1)
    else:
        console.print("\n[bold green]🎉 同步完成！[/bold green]")


@cli.command()
@click.argument("page", metavar="PAGE_ID_OR_URL")
def status(page: str) -> None:
    """查看某 Notion 页面的上次同步状态。"""
    load_dotenv()
    page_id = _extract_page_id(page)
    cfg     = load_config()
    db_path = Path(cfg.state_file) if cfg.state_file else Path(".codegen_state.db")

    with StateDB(db_path) as db:
        record = db.get_record(page_id)

    if record is None:
        console.print(f"[yellow]页面 {page_id} 从未同步过。[/yellow]")
    else:
        console.print(
            f"页面 ID      : [cyan]{record['page_id']}[/cyan]\n"
            f"Notion 编辑时间: [cyan]{record['last_edited_at']}[/cyan]\n"
            f"本机同步时间  : [cyan]{record['synced_at']}[/cyan]"
        )


@cli.command()
@click.confirmation_option(prompt="确认清空所有同步状态？（下次运行将全量同步）")
def reset() -> None:
    """清空所有同步状态（下次将全量同步）。"""
    load_dotenv()
    cfg     = load_config()
    db_path = Path(cfg.state_file) if cfg.state_file else Path(".codegen_state.db")

    with StateDB(db_path) as db:
        db.clear()

    console.print("[green]✅ 同步状态已清空。[/green]")


# ── 辅助：递归收集所有页面 ────────────────────────────────────

def _collect_all_pages(page: object) -> list:
    """
    递归收集一个 NotionPage 及其所有子页面，返回扁平列表。
    顺序：父页面在前，子页面在后（DFS 前序）。
    """
    from .notion_reader import NotionPage  # 避免循环导入

    result: list[NotionPage] = [page]  # type: ignore[list-item]
    for subpage in page.subpages:      # type: ignore[union-attr]
        result.extend(_collect_all_pages(subpage))
    return result


# ── __main__ 入口 ─────────────────────────────────────────────

if __name__ == "__main__":
    cli()