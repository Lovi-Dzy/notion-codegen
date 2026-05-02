# notion_codegen/executor.py
"""
文件操作执行器。

职责：
    接收 FileOperation 列表，按顺序在本地文件系统执行每一项操作。
    提供 dry_run 模式（只打印，不写磁盘）方便调试。

执行语义：
    create          若文件已存在 → 跳过（幂等）；否则写入
    modify:replace  直接覆盖（文件不存在时自动创建）
    modify:patch    调用 patcher 应用差异后写回
    delete          若文件存在则删除；不存在则跳过（幂等）

执行结果：
    每个操作返回一个 OperationResult，汇总为 ExecutionSummary。
    即使部分操作失败，其余操作仍会继续执行（除非 fail_fast=True）。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.table import Table

from .parser import FileOperation, OpType
from .patcher import PatchError, apply_patch

console = Console()


# ── 结果数据结构 ──────────────────────────────────────────────

class ResultStatus(Enum):
    OK      = "ok"
    SKIPPED = "skipped"   # create 时文件已存在；delete 时文件不存在
    FAILED  = "failed"


@dataclass
class OperationResult:
    operation: FileOperation
    status:    ResultStatus
    message:   str = ""
    error:     Optional[Exception] = None


@dataclass
class ExecutionSummary:
    results: list[OperationResult] = field(default_factory=list)

    @property
    def ok_count(self)      -> int: return sum(1 for r in self.results if r.status == ResultStatus.OK)
    @property
    def skipped_count(self) -> int: return sum(1 for r in self.results if r.status == ResultStatus.SKIPPED)
    @property
    def failed_count(self)  -> int: return sum(1 for r in self.results if r.status == ResultStatus.FAILED)
    @property
    def has_failures(self)  -> bool: return self.failed_count > 0

    def print_summary(self) -> None:
        """用 rich 打印执行结果汇总表格。"""
        table = Table(title="执行结果", show_header=True, header_style="bold cyan")
        table.add_column("操作",   style="dim",    width=16)
        table.add_column("状态",                   width=10)
        table.add_column("文件路径")
        table.add_column("备注")

        for r in self.results:
            status_str, status_style = {
                ResultStatus.OK:      ("✅ OK",      "green"),
                ResultStatus.SKIPPED: ("⏭  跳过",   "yellow"),
                ResultStatus.FAILED:  ("❌ 失败",    "red"),
            }[r.status]

            table.add_row(
                r.operation.op_type.value,
                f"[{status_style}]{status_str}[/{status_style}]",
                str(r.operation.file_path),
                r.message,
            )

        console.print(table)
        console.print(
            f"[bold]汇总[/bold]: "
            f"[green]{self.ok_count} 成功[/green]  "
            f"[yellow]{self.skipped_count} 跳过[/yellow]  "
            f"[red]{self.failed_count} 失败[/red]"
        )


# ── 执行器 ────────────────────────────────────────────────────

class Executor:
    """
    将 FileOperation 列表落地到文件系统。

    Args:
        dry_run:   True 时只打印操作，不实际写磁盘。
        fail_fast: True 时遇到第一个错误立即停止。
    """

    def __init__(self, dry_run: bool = False, fail_fast: bool = False) -> None:
        self.dry_run   = dry_run
        self.fail_fast = fail_fast

    def execute(self, ops: list[FileOperation]) -> ExecutionSummary:
        """
        顺序执行所有操作，返回汇总结果。

        Args:
            ops: 由 PageParser 生成的 FileOperation 列表。

        Returns:
            ExecutionSummary，包含每个操作的结果。
        """
        summary = ExecutionSummary()

        for op in ops:
            result = self._execute_one(op)
            summary.results.append(result)

            if result.status == ResultStatus.FAILED and self.fail_fast:
                console.print(
                    "[bold red]fail_fast=True，遇到错误后中止执行。[/bold red]"
                )
                break

        return summary

    # ── 单条操作分发 ──────────────────────────────────────────

    def _execute_one(self, op: FileOperation) -> OperationResult:
        """分发到对应的处理方法，捕获所有异常转为 FAILED 结果。"""
        try:
            handler = {
                OpType.CREATE:  self._do_create,
                OpType.REPLACE: self._do_replace,
                OpType.PATCH:   self._do_patch,
                OpType.DELETE:  self._do_delete,
            }[op.op_type]
            return handler(op)
        except Exception as exc:  # noqa: BLE001
            msg = f"{type(exc).__name__}: {exc}"
            console.print(f"[red]❌ {op.op_type.value} {op.file_path}\n   {msg}[/red]")
            return OperationResult(op, ResultStatus.FAILED, msg, exc)

    # ── 各操作实现 ────────────────────────────────────────────

    def _do_create(self, op: FileOperation) -> OperationResult:
        if op.file_path.exists():
            msg = "文件已存在，跳过"
            console.print(f"[yellow]⏭  create (skip) {op.file_path}[/yellow]")
            return OperationResult(op, ResultStatus.SKIPPED, msg)

        if not self.dry_run:
            op.file_path.parent.mkdir(parents=True, exist_ok=True)
            op.file_path.write_text(op.content or "", encoding="utf-8")

        console.print(f"[green]✨ create {'(dry)' if self.dry_run else ''} {op.file_path}[/green]")
        return OperationResult(op, ResultStatus.OK, "已创建")

    def _do_replace(self, op: FileOperation) -> OperationResult:
        exists = op.file_path.exists()
        if not self.dry_run:
            op.file_path.parent.mkdir(parents=True, exist_ok=True)
            op.file_path.write_text(op.content or "", encoding="utf-8")

        action = "覆盖" if exists else "新建(replace)"
        console.print(f"[green]✏️  replace {'(dry)' if self.dry_run else ''} {op.file_path}[/green]")
        return OperationResult(op, ResultStatus.OK, action)

    def _do_patch(self, op: FileOperation) -> OperationResult:
        if not op.file_path.exists():
            raise FileNotFoundError(
                f"modify:patch 目标文件不存在：{op.file_path}"
            )

        if not self.dry_run:
            new_content = apply_patch(op.file_path, op.content or "")
            op.file_path.write_text(new_content, encoding="utf-8")

        console.print(f"[green]🔧 patch {'(dry)' if self.dry_run else ''} {op.file_path}[/green]")
        return OperationResult(op, ResultStatus.OK, "patch 已应用")

    def _do_delete(self, op: FileOperation) -> OperationResult:
        if not op.file_path.exists():
            msg = "文件不存在，跳过"
            console.print(f"[yellow]⏭  delete (skip) {op.file_path}[/yellow]")
            return OperationResult(op, ResultStatus.SKIPPED, msg)

        if not self.dry_run:
            op.file_path.unlink()

        console.print(f"[green]🗑️  delete {'(dry)' if self.dry_run else ''} {op.file_path}[/green]")
        return OperationResult(op, ResultStatus.OK, "已删除")