# notion-codegen

将 Notion 页面同步为本地代码文件的命令行工具。

你在 Notion 中维护项目架构和代码模板，运行一条命令就能将它同步到本地文件系统。
支持增量同步（只同步有变更的页面）和四种文件操作类型。

## 项目结构概览

本项目包含两个子系统：

| 子系统 | 技术栈 | 说明 |
|--------|--------|------|
| **notion-codegen CLI** | Python (Click) | 核心同步工具，将 Notion 页面解析为本地文件 |
| **Word Format Agent (WFA)** | TypeScript (Fastify + Next.js + BullMQ) | Web 管理平台，提供文档上传、AI 排版、DOCX 生成等功能 |

CLI 是独立可用的工具；WFA Web 平台是配套的可视化管理界面（开发中）。

## 快速开始

### 1. 安装依赖

    python -m venv .venv
    .venv\Scripts\Activate.ps1   # Windows PowerShell
    pip install -r requirements.txt

### 2. 配置 Notion Token

复制 `.env.example` 为 `.env` 并填写你的 Notion Integration Token：

    NOTION_TOKEN=secret_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx

如何获取 Token：Notion 设置 → Integrations → 新建 Integration → 复制 Secret。
记得将该 Integration 共享到目标页面（页面右上角 … → 连接）。

### 3. 配置输出目录（可选）

将 `.codegen.toml` 中的 `output_dir` 改为你的项目路径：

    [codegen]
    output_dir = "D:/Projects/my-app"

### 4. 运行同步

    python -m notion_codegen sync <page_id_or_url>

## Notion 页面格式

工具识别 Notion 页面中特定格式的块作为文件条目。

### 文件条目格式

每个文件条目由两部分组成：

1. H3 标题，格式为：  `路径` | 操作类型
2. 紧随其后的代码块（文件内容）

示例：

    ### `src/main.py` | create
    （代码块：文件内容）

### 操作类型

| 操作            | 语义                       |
|-----------------|----------------------------|
| create          | 创建新文件，若已存在则跳过  |
| modify:replace  | 整体替换文件内容            |
| modify:patch    | 精准打 patch（见下方）      |
| delete          | 删除文件（不需要代码块）    |

### modify:patch 格式

    <<<<<<< OLD
    这里是要被替换的旧内容
    =======
    这里是新内容
    >>>>>>> NEW

单个文件可包含多个 hunk，每个 hunk 独立应用。

### 子页面分组

标题以 📁 开头的子页面会被递归解析，适合按目录组织文件条目。

## 命令参考

    # 同步（增量，只同步有变更的页面）
    python -m notion_codegen sync <page_id_or_url>

    # 指定输出目录
    python -m notion_codegen sync <page_id_or_url> --output D:/Projects/my-app

    # Dry-run 预览（不写磁盘）
    python -m notion_codegen sync <page_id_or_url> --dry-run

    # 强制全量重新同步
    python -m notion_codegen sync <page_id_or_url> --force

    # 查看某页面的同步状态
    python -m notion_codegen status <page_id_or_url>

    # 清空状态缓存（下次将全量同步）
    python -m notion_codegen reset

## 项目结构

    notion-codegen/
    ├── notion_codegen/            # Python CLI 核心
    │   ├── __init__.py            包声明与版本
    │   ├── __main__.py            python -m notion_codegen 入口
    │   ├── cli.py                 CLI 命令定义
    │   ├── config.py              .codegen.toml 配置加载
    │   ├── log.py                 日志配置（rotating file handler）
    │   ├── notion_reader.py       Notion API 页面读取（支持并发）
    │   ├── parser.py              块结构 → FileOperation 解析
    │   ├── patcher.py             modify:patch 差异应用
    │   ├── executor.py            文件操作执行（支持 hash 去重 + 备份）
    │   └── state.py               SQLite 增量状态追踪（页面级 + 文件级）
    ├── apps/                      # WFA Web 平台（TypeScript）
    │   ├── api/                   Fastify REST API
    │   ├── worker/                BullMQ 后台任务处理
    │   └── web/                   Next.js 前端
    ├── packages/shared/           WFA 共享模块（类型、LLM 网关）
    ├── .codegen.toml
    ├── .env
    ├── .env.example
    ├── .gitignore
    ├── pyproject.toml
    ├── requirements.txt
    └── README.md

## 开发 / 自定义

各模块均是独立的纯 Python 文件，可直接导入使用：

    from notion_codegen.notion_reader import NotionReader, NotionPage
    from notion_codegen.parser import PageParser, FileOperation, OpType
    from notion_codegen.executor import Executor, ExecutionSummary
    from notion_codegen.patcher import apply_patch
    from notion_codegen.state import StateDB