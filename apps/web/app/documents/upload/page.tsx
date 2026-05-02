'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useRef, useState } from 'react'
import { listFormatConfigs, uploadDocument, uploadDocx } from '../../../lib/api'

type UploadMode = 'markdown' | 'docx'

function modeLabel(mode: UploadMode): string {
  return mode === 'markdown' ? 'Markdown / TXT' : 'DOCX 文档'
}

export default function DocumentUploadPage() {
  const router = useRouter()
  const fileRef = useRef<HTMLInputElement>(null)
  const [mode, setMode] = useState<UploadMode>('markdown')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  const accept =
    mode === 'markdown'
      ? '.md,.txt,text/markdown,text/plain'
      : '.docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document'

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const file = fileRef.current?.files?.[0]
    if (!file) {
      setMessage('请选择文件')
      return
    }

    setLoading(true)
    setMessage(null)

    try {
      let result
      if (mode === 'docx') {
        result = await uploadDocx({ file })
      } else {
        result = await uploadDocument({ file })
      }
      router.push(`/documents/${result.document.id}`)
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '上传失败')
      setLoading(false)
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <p className="eyebrow">Upload</p>
        <h1>上传文档</h1>
        <p className="subtitle">
          支持 Markdown / TXT（轻量解析）和 DOCX（自动提取文本后解析）两种模式。
        </p>
        <p className="subtitle">
          <Link href="/documents">← 返回文档列表</Link>
        </p>
      </section>

      {/* 模式切换 */}
      <section className="card wide" style= marginBottom: '18px' >
        <h2>选择上传模式</h2>
        <div className="buttonGroup" style= marginTop: '12px' >
          <button
            type="button"
            className={mode === 'markdown' ? 'button' : 'button buttonGhost'}
            onClick={() => {
              setMode('markdown')
              setMessage(null)
              if (fileRef.current) fileRef.current.value = ''
            }}
          >
            📄 Markdown / TXT
          </button>
          <button
            type="button"
            className={mode === 'docx' ? 'button' : 'button buttonGhost'}
            onClick={() => {
              setMode('docx')
              setMessage(null)
              if (fileRef.current) fileRef.current.value = ''
            }}
          >
            📝 DOCX 文档
          </button>
        </div>

        <div className="card soft" style= marginTop: '14px' >
          {mode === 'markdown' ? (
            <p className="muted small">
              <strong>Markdown / TXT 模式</strong>：直接解析文本结构。
              文件格式：<code>.md</code> / <code>.txt</code>。
              解析速度快，适合已有 Markdown 格式的论文草稿。
            </p>
          ) : (
            <p className="muted small">
              <strong>DOCX 模式</strong>：Worker 使用 mammoth 将 DOCX 转为 Markdown，再解析结构。
              文件格式：<code>.docx</code>。
              适合直接上传已有的 Word 文档，保留标题层级和基本格式。
            </p>
          )}
        </div>
      </section>

      {/* 上传表单 */}
      <section className="card wide">
        <h2>上传 {modeLabel(mode)}</h2>
        <form className="form" onSubmit={(e) => void handleSubmit(e)}>
          <label className="field">
            <span className="label">选择文件</span>
            <input
              ref={fileRef}
              key={mode}
              className="input"
              type="file"
              accept={accept}
              disabled={loading}
            />
          </label>

          <div className="buttonGroup">
            <button className="button" type="submit" disabled={loading}>
              {loading ? '上传中...' : `上传并解析`}
            </button>
            <Link className="button buttonGhost" href="/documents">
              取消
            </Link>
          </div>

          {message ? (
            <p className={message.includes('失败') || message.includes('Error') ? 'errorText' : 'successText'}>
              {message}
            </p>
          ) : null}
        </form>
      </section>
    </main>
  )
}