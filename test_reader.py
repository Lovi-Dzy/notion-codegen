# test_reader.py（测试完可删除）
from dotenv import load_dotenv
import os

load_dotenv()

from notion_codegen.notion_reader import NotionReader

token = os.getenv("NOTION_TOKEN", "")
page_id = os.getenv("NOTION_PAGE_ID", "")

if not token or not page_id:
    print("错误：请确保 .env 中已填写 NOTION_TOKEN 和 NOTION_PAGE_ID")
    exit(1)

print(f"\n🔍 开始读取页面 {page_id}...\n")

reader = NotionReader(token=token)
page = reader.read_page(page_id)

print(f"✅ 主页面：{page.title}")
print(f"   块数量：{len(page.blocks)}")
print(f"   子页面数量：{len(page.subpages)}")
print(f"   最后编辑：{page.last_edited_time}")

if page.subpages:
    print("\n📁 子页面列表：")
    for sub in page.subpages:
        print(f"   - {sub.title} ({len(sub.blocks)} 块)")

print("\n🔍 增量同步用 last_edited_time 映射：")
edited_map = reader.get_last_edited_map(page_id)
for pid, ts in edited_map.items():
    print(f"   {pid[:8]}...  {ts}")

print("\n🎉 Phase 2 验证通过！")