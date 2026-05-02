# test_executor.py（测试完可删除）
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

from notion_codegen.notion_reader import NotionReader
from notion_codegen.parser import PageParser
from notion_codegen.executor import Executor

token   = os.getenv("NOTION_TOKEN", "")
page_id = os.getenv("NOTION_PAGE_ID", "")

if not token or not page_id:
    print("错误：请确保 .env 中已填写 NOTION_TOKEN 和 NOTION_PAGE_ID")
    exit(1)

OUTPUT_DIR = Path("D:/tmp/codegen-test")

print(f"\n🔍 读取页面 {page_id}...")
reader = NotionReader(token=token)
page   = reader.read_page(page_id)

print(f"\n🔧 解析文件操作...")
parser = PageParser()
ops    = parser.parse(page, output_dir=OUTPUT_DIR)

if not ops:
    print("⚠  未解析到任何文件操作，请检查 Notion 页面格式。")
    exit(0)

print(f"\n▶  Dry-run 预览（不会写入磁盘）：")
exec_dry = Executor(dry_run=True)
summary_dry = exec_dry.execute(ops)
summary_dry.print_summary()

answer = input("\n❓ 是否正式执行到本地？(y/N) ").strip().lower()
if answer == "y":
    print(f"\n▶  正式执行 → {OUTPUT_DIR}")
    executor = Executor(dry_run=False)
    summary  = executor.execute(ops)
    summary.print_summary()

    if summary.has_failures:
        print("\n⚠  部分操作失败，请查看上方错误信息。")
    else:
        print("\n🎉 Phase 4 验证通过！")
else:
    print("已取消正式执行。")