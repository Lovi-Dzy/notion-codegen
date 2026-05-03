# notion_codegen/patcher.py
"""
modify:patch 操作的差异应用模块。

支持两种 patch 格式（自动检测）：
  1. 自定义三路合并格式（优先）：
       <<<<<<< OLD
       <旧内容>
       =======
       <新内容>
       >>>>>>> NEW
     支持单文件中出现多个 hunk（每个 hunk 独立替换）。
     也支持 <<<<<<< OLD:N 指定替换第 N 次匹配（0-indexed）。

  2. 统一 diff 格式（fallback）：
       --- a/file
       +++ b/file
       @@ ... @@
       -旧行
       +新行
     通过 diff-match-patch 库应用，适合 AI 生成的标准 diff 输出。

异常体系：
  PatchError         基类，所有 patch 失败都抛此异常
  HunkNotFoundError  某个 hunk 的 OLD 内容在原文件中找不到
  AmbiguousHunkError 某个 hunk 的 OLD 内容在原文件中出现多次
"""
from __future__ import annotations

import re
from pathlib import Path

from .log import get_logger

logger = get_logger("patcher")


# ── 异常 ─────────────────────────────────────────────────────

class PatchError(Exception):
    """所有 patch 失败的基类异常。"""


class HunkNotFoundError(PatchError):
    """OLD 内容在文件中找不到。"""

    def __init__(
        self, file_path: Path, hunk_index: int, old_text: str, original: str
    ) -> None:
        self.file_path  = file_path
        self.hunk_index = hunk_index
        self.old_text   = old_text

        # 尝试找相似行（OLD 的首尾行在原文中出现的位置）
        hint = _find_similar_lines(old_text, original)
        hint_str = ""
        if hint:
            hint_str = "\n\n可能的匹配位置（行号）:\n" + "\n".join(
                f"  行 {ln}: {text!r}" for ln, text in hint
            )

        super().__init__(
            f"Hunk #{hunk_index} not found in {file_path}\n"
            f"Expected OLD content (first 120 chars):\n{old_text[:120]!r}"
            f"{hint_str}"
        )


class AmbiguousHunkError(PatchError):
    """OLD 内容在文件中出现多次，无法确定替换位置。"""

    def __init__(
        self,
        file_path: Path,
        hunk_index: int,
        count: int,
        line_numbers: list[int],
        old_text: str,
    ) -> None:
        self.file_path    = file_path
        self.hunk_index   = hunk_index
        self.count        = count
        self.line_numbers = line_numbers
        self.old_text     = old_text

        locs = ", ".join(f"行 {ln}" for ln in line_numbers[:5])
        if len(line_numbers) > 5:
            locs += f" ... 共 {count} 处"

        super().__init__(
            f"Hunk #{hunk_index} matches {count} locations in {file_path} ({locs}).\n"
            f"请使 OLD 内容更具体，或使用 <<<<<<< OLD:N 指定第 N 次匹配（0-indexed）。"
        )


def _find_similar_lines(
    old_text: str, original: str, max_results: int = 3
) -> list[tuple[int, str]]:
    """
    在 original 中查找与 old_text 首行/末行相似的行。
    返回 [(行号, 该行文本), ...]，最多 max_results 条。
    """
    old_lines = old_text.strip().splitlines()
    if not old_lines:
        return []

    first_line = old_lines[0].strip()
    last_line = old_lines[-1].strip()

    # 取长度 >= 4 的行作为模糊搜索目标
    targets = [l for l in (first_line, last_line) if len(l) >= 4]
    if not targets:
        return []

    results: list[tuple[int, str]] = []
    orig_lines = original.splitlines()
    for i, line in enumerate(orig_lines, start=1):
        stripped = line.strip()
        for target in targets:
            # 包含目标的核心片段（去掉首尾空白后仍匹配）
            if target in stripped or stripped in target:
                results.append((i, stripped[:80]))
                if len(results) >= max_results:
                    return results
                break
    return results


def _find_match_lines(old_text: str, original: str) -> list[int]:
    """返回 old_text 在 original 中每次出现的起始行号。"""
    lines = original.splitlines(keepends=True)
    old_lines = old_text.splitlines(keepends=True)
    if not old_lines:
        return []

    result: list[int] = []
    for i in range(len(lines) - len(old_lines) + 1):
        if lines[i : i + len(old_lines)] == old_lines:
            result.append(i + 1)  # 1-indexed
    return result


# ── 三路合并格式解析 ──────────────────────────────────────────

# 匹配一个完整的 hunk：
#   <<<<<<< OLD[:N]
#   <任意内容（含换行）>
#   =======
#   <任意内容（含换行）>
#   >>>>>>> NEW
_HUNK_RE = re.compile(
    r"<<<<<<< OLD(?::(\d+))?\n(.*?)=======\n(.*?)>>>>>>> NEW",
    re.DOTALL,
)


def _apply_custom_format(original: str, patch_text: str, file_path: Path) -> str:
    """
    应用自定义三路合并格式的 patch。

    按顺序逐个应用 hunk，每次在当前文本上做精确字符串替换。
    支持 <<<<<<< OLD:N 指定替换第 N 次匹配（0-indexed）。
    """
    hunks = _HUNK_RE.findall(patch_text)
    if not hunks:
        raise PatchError(
            f"patch 文本中未找到任何 hunk（<<<<<<< OLD ... >>>>>>> NEW）: {file_path}"
        )

    result = original
    for idx, (match_index_str, old_text, new_text) in enumerate(hunks):
        match_index = int(match_index_str) if match_index_str else None
        count = result.count(old_text)

        if count == 0:
            raise HunkNotFoundError(file_path, idx, old_text, original)

        if match_index is not None:
            # 指定了匹配序号
            if match_index >= count:
                raise PatchError(
                    f"Hunk #{idx}: <<<<<<< OLD:{match_index} 超出范围，"
                    f"文件中只找到 {count} 处匹配 ({file_path})"
                )
            # 逐个替换直到到达目标序号
            pos = -1
            for _ in range(match_index + 1):
                pos = result.index(old_text, pos + 1)
            result = result[:pos] + new_text + result[pos + len(old_text):]
        elif count > 1:
            line_numbers = _find_match_lines(old_text, original)
            raise AmbiguousHunkError(file_path, idx, count, line_numbers, old_text)
        else:
            result = result.replace(old_text, new_text, 1)

    return result


# ── 统一 diff 格式（fallback）────────────────────────────────

def _apply_unified_diff(original: str, patch_text: str, file_path: Path) -> str:
    """
    使用 diff-match-patch 应用统一 diff 格式的 patch（fallback）。

    如果 diff-match-patch 未安装，直接抛出 PatchError 提示用户安装。
    """
    try:
        import diff_match_patch as dmp_module  # type: ignore
    except ImportError as exc:
        raise PatchError(
            "检测到统一 diff 格式，但 diff-match-patch 未安装。\n"
            "请运行：pip install diff-match-patch"
        ) from exc

    dmp    = dmp_module.diff_match_patch()
    patches = dmp.patch_fromText(patch_text)
    new_text, results = dmp.patch_apply(patches, original)

    failed = [i for i, ok in enumerate(results) if not ok]
    if failed:
        raise PatchError(
            f"{file_path}: {len(failed)} 个 diff hunk 应用失败 (indices: {failed})"
        )

    return new_text


# ── 公开入口 ──────────────────────────────────────────────────

def apply_patch(file_path: Path, patch_text: str) -> str:
    """
    对 file_path 指向的文件应用 patch_text，返回新的文件内容。

    自动检测 patch 格式：
      - 包含 '<<<<<<< OLD' → 自定义三路合并格式
      - 否则 → 统一 diff 格式（需要 diff-match-patch）

    Args:
        file_path:  目标文件路径（需已存在）。
        patch_text: patch 文本内容。

    Returns:
        应用 patch 后的新文件内容字符串。

    Raises:
        FileNotFoundError:  file_path 不存在。
        HunkNotFoundError:  某个 hunk 的 OLD 内容找不到。
        AmbiguousHunkError: 某个 hunk 的 OLD 内容出现多次。
        PatchError:         其他 patch 失败情况。
    """
    if not file_path.exists():
        raise FileNotFoundError(
            f"modify:patch 目标文件不存在：{file_path}"
        )

    original = file_path.read_text(encoding="utf-8")

    if "<<<<<<< OLD" in patch_text:
        return _apply_custom_format(original, patch_text, file_path)
    else:
        return _apply_unified_diff(original, patch_text, file_path)
