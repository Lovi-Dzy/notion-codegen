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


# ── 异常 ─────────────────────────────────────────────────────

class PatchError(Exception):
    """所有 patch 失败的基类异常。"""


class HunkNotFoundError(PatchError):
    """OLD 内容在文件中找不到。"""
    def __init__(self, file_path: Path, hunk_index: int, old_text: str) -> None:
        self.file_path  = file_path
        self.hunk_index = hunk_index
        self.old_text   = old_text
        super().__init__(
            f"Hunk #{hunk_index} not found in {file_path}\n"
            f"Expected OLD content (first 120 chars):\n{old_text[:120]!r}"
        )


class AmbiguousHunkError(PatchError):
    """OLD 内容在文件中出现多次，无法确定替换位置。"""
    def __init__(self, file_path: Path, hunk_index: int, count: int) -> None:
        self.file_path  = file_path
        self.hunk_index = hunk_index
        self.count      = count
        super().__init__(
            f"Hunk #{hunk_index} matches {count} locations in {file_path}. "
            f"Please make OLD content more specific."
        )


# ── 三路合并格式解析 ──────────────────────────────────────────

# 匹配一个完整的 hunk：
#   <<<<<<< OLD\
#   <任意内容（含换行）>
#   =======
#   <任意内容（含换行）>
#   >>>>>>> NEW
_HUNK_RE = re.compile(
    r"<<<<<<< OLD\n(.*?)=======\n(.*?)>>>>>>> NEW",
    re.DOTALL,
)


def _apply_custom_format(original: str, patch_text: str, file_path: Path) -> str:
    """
    应用自定义三路合并格式的 patch。

    按顺序逐个应用 hunk，每次在当前文本上做精确字符串替换。
    hunk 中 OLD/NEW 内容末尾若没有换行，不额外追加，以保持原样。
    """
    hunks = _HUNK_RE.findall(patch_text)
    if not hunks:
        raise PatchError(
            f"patch 文本中未找到任何 hunk（<<<<<<< OLD ... >>>>>>> NEW）: {file_path}"
        )

    result = original
    for idx, (old_text, new_text) in enumerate(hunks):
        count = result.count(old_text)
        if count == 0:
            raise HunkNotFoundError(file_path, idx, old_text)
        if count > 1:
            raise AmbiguousHunkError(file_path, idx, count)
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