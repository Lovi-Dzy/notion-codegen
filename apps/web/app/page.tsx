import Link from 'next/link'
import { getHealth, listDocuments, listFormatConfigs } from '../lib/api'

export default async function HomePage() {
  const [health, docList, configList] = await Promise.allSettled([
    getHealth(),
    listDocuments(),
    listFormatConfigs(),
  ])

  const apiOnline =
    health.status === 'fulfilled' && health.value !== null
  const recentDocs =
    docList.status === 'fulfilled' ? docList.value.documents.slice(0, 5) : []
  const configCount =
    configList.status === 'fulfilled' ? configList.value.configs.length : 0

  return (
    <main className="page">
      <section className="hero">
        <p className="eyebrow">Word Format Agent</p>
        <h1>论文格式自动化平台</h1>
        <p className="subtitle">
          上传 Markdown / DOCX 文档，AI 解析结构、生成符合规范的 Word 文件；支持 AI 对话修改、手动编辑器、模板反向学习。
        </p>
        <div className="buttonGroup">
          <Link className="button" href="/documents/upload">
            上传文档
          </Link>
          <Link className="button buttonSecondary" href="/documents">
            文档列表
          </Link>
          <Link className="button buttonGhost" href="/templates/upload">
            上传模板
          </Link>
        </div>
      </section>

      <section className="grid">
        {/* 系统状态 */}
        <article className="card">
          <h2>系统状态</h2>
          <div className="row">
            <span>API</span>
            <span className={`badge ${apiOnline ? 'success' : 'error'}`}>
              {apiOnline ? '在线' : '离线'}
            </span>
          </div>
          <div className="row">
            <span>格式配置</span>
            <strong>{configCount} 个</strong>
          </div>
          <div className="row">
            <span>近期文档</span>
            <strong>{recentDocs.length} 条</strong>
          </div>
        </article>

        {/* 快速操作 */}
        <article className="card">
          <h2>快速操作</h2>
          <div className="list">
            <div className="listItem">
              <Link href="/documents/upload">📄 上传 Markdown / DOCX 文档</Link>
            </div>
            <div className="listItem">
              <Link href="/templates/upload">📐 上传 DOCX 模板（反向学习）</Link>
            </div>
            <div className="listItem">
              <Link href="/configs">⚙️ 管理格式配置</Link>
            </div>
            <div className="listItem">
              <Link href="/documents">📋 查看所有文档</Link>
            </div>
          </div>
        </article>

        {/* 近期文档 */}
        <article className="card">
          <h2>近期文档</h2>
          {recentDocs.length === 0 ? (
            <p className="muted">暂无文档。上传第一份文档开始使用。</p>
          ) : (
            <ul className="list">
              {recentDocs.map((doc) => (
                <li className="listItem" key={doc.id}>
                  <Link href={`/documents/${doc.id}`}>
                    {doc.originalFileName ?? doc.id}
                  </Link>
                  <span className="muted small">{doc.status}</span>
                </li>
              ))}
            </ul>
          )}
          {recentDocs.length > 0 ? (
            <div style= marginTop: '12px' >
              <Link className="button buttonGhost" href="/documents">
                查看全部 →
              </Link>
            </div>
          ) : null}
        </article>
      </section>

      {/* 功能说明 */}
      <section className="grid" style= marginTop: '18px' >
        <article className="card wide">
          <h2>核心功能一览</h2>
          <section className="grid">
            <div className="card half soft">
              <h3>📄 文档解析</h3>
              <p className="muted small">
                上传 .md / .txt / .docx，AI 识别标题层级、摘要、关键词、参考文献等结构，生成结构化 AST。
              </p>
            </div>
            <div className="card half soft">
              <h3>📝 DOCX 生成</h3>
              <p className="muted small">
                根据 FormatConfig 规范，使用 Pandoc 将 AST 渲染为符合论文格式要求的 Word 文档，附带 PDF 预览。
              </p>
            </div>
            <div className="card half soft">
              <h3>🛡️ Safety Gate</h3>
              <p className="muted small">
                AI 修改后自动检查正文相似度，文本变更过大时阻断并要求人工授权，保护原文安全。
              </p>
            </div>
            <div className="card half soft">
              <h3>✏️ 低配 Word 编辑器</h3>
              <p className="muted small">
                在浏览器中手动调整 Block 类型、标题层级、对齐方式和文本，保存后自动重生成 DOCX。
              </p>
            </div>
            <div className="card half soft">
              <h3>🤖 AI 对话修改</h3>
              <p className="muted small">
                用自然语言描述修改意图，AI 解析指令并生成 Patch，应用到 AST 后自动重新排版。
              </p>
            </div>
            <div className="card half soft">
              <h3>📐 模板反向学习</h3>
              <p className="muted small">
                上传已排好格式的 DOCX 模板，系统解析 OpenXML 样式，自动生成格式配置草稿，支持版本对比与回滚。
              </p>
            </div>
          </section>
        </article>
      </section>
    </main>
  )
}