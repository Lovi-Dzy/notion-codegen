import Link from 'next/link'
import { listDocuments } from '../../lib/api'

function statusLabel(status: string): string {
  const labels: Record<string, string> = {
    draft: '草稿',
    uploaded: '已上传',
    parsing: '解析中',
    parsed: '已解析',
    generating: '生成中',
    safety_blocked: '安全阻断',
    ready: '可下载',
    failed: '失败',
  }
  return labels[status] ?? status
}

function statusTone(status: string): string {
  if (status === 'ready') return 'success'
  if (status === 'failed' || status === 'safety_blocked') return 'error'
  if (status === 'parsing' || status === 'generating') return 'warning'
  return 'accent'
}

export default async function DocumentsPage() {
  let documents: Awaited<ReturnType<typeof listDocuments>>['documents'] = []
  let loadError: string | null = null

  try {
    const result = await listDocuments()
    documents = result.documents
  } catch (err) {
    loadError = err instanceof Error ? err.message : '加载失败'
  }

  return (
    <main className="page">
      <section className="hero">
        <p className="eyebrow">Documents</p>
        <h1>文档列表</h1>
        <p className="subtitle">共 {documents.length} 条文档</p>
        <div className="buttonGroup">
          <Link className="button" href="/documents/upload">
            + 上传新文档
          </Link>
          <Link className="button buttonGhost" href="/">
            ← 返回首页
          </Link>
        </div>
      </section>

      {loadError ? (
        <div className="errorBox">{loadError}</div>
      ) : documents.length === 0 ? (
        <article className="card wide">
          <h2>暂无文档</h2>
          <p className="muted">点击"上传新文档"开始使用。</p>
        </article>
      ) : (
        <section className="grid">
          <article className="card wide">
            <ul className="list">
              {documents.map((doc) => (
                <li className="listItem" key={doc.id}>
                  <div className="cardHeader">
                    <div className="cardTitleGroup">
                      <h3>
                        <Link href={`/documents/${doc.id}`}>
                          {doc.originalFileName ?? doc.id}
                        </Link>
                      </h3>
                      <span className="muted small">
                        ID: {doc.id} · 更新：{new Date(doc.updatedAt).toLocaleString('zh-CN')}
                      </span>
                    </div>
                    <div className="actions">
                      <span className={`badge ${statusTone(doc.status)}`}>
                        {statusLabel(doc.status)}
                      </span>
                      {doc.hasDocx ? <span className="badge success">DOCX ✓</span> : null}
                      {doc.hasPdfPreview ? <span className="badge success">PDF ✓</span> : null}
                    </div>
                  </div>
                  <div className="buttonGroup" style= marginTop: '8px' >
                    <Link className="button buttonGhost" href={`/documents/${doc.id}`}>
                      查看详情
                    </Link>
                    {doc.hasDocx ? (
                      <a
                        className="button buttonSecondary"
                        href={`${process.env.NEXT_PUBLIC_API_BASE_URL ?? 'http://localhost:4000'}/documents/${doc.id}/download/docx`}
                      >
                        下载 DOCX
                      </a>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          </article>
        </section>
      )}
    </main>
  )
}