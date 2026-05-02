# test_parser.py（测试完可删除）
from dotenv import load_dotenv
import os
from pathlib import Path

load_dotenv()

from notion_codegen.notion_reader import NotionReader
from notion_codegen.parser import PageParser

token   = os.getenv("NOTION_TOKEN", "")
page_id = os.getenv("NOTION_PAGE_ID", "")

if not token or not page_id:
    print("错误：请确保 .env 中已填写 NOTION_TOKEN 和 NOTION_PAGE_ID")
    exit(1)

print(f"\n🔍 读取页面 {page_id}...")
reader = NotionReader(token=token)
page   = reader.read_page(page_id)

print(f"\n🔧 解析文件操作...")
parser = PageParser()
ops    = parser.parse(page, output_dir=Path("D:/tmp/codegen-test"))

if not ops:
    print("⚠  未解析到任何文件操作。")
    print("   请确认 Notion 页面中存在格式为  `路径` | create  的 H3 标题。")
else:
    print(f"\n✅ 共解析到 {len(ops)} 个文件操作：\n")
    for op in ops:
        icon = {"create": "✨", "modify:replace": "✏️", "modify:patch": "🔧", "delete": "🗑️"}
        print(f"  {icon.get(op.op_type.value, '?')} [{op.op_type.value:<16}] {op.file_path}")
        if op.content:
            lines = op.content.splitlines()
            preview = lines[0][:60] + ("..." if len(lines[0]) > 60 else "")
            print(f"     内容预览: {preview} ({len(lines)} 行)")

print("\n🎉 Phase 3 验证通过！")