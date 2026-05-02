import Link from 'next/link'
import { listFormatConfigs } from '../../lib/api'

function sourceLabel(source: string): string {
  const labels: Record<string, string> = {
    BUILTIN: '内置',
    USER: '用户',
    IMPORTED: '模板导入',
    WIZARD: '向导',
    AI: 'AI 生成',
  }
  return labels[source] ?? source
}

export default async function ConfigsPage() {
  let configs: Awaited<ReturnType<typeof listFormatConfigs>>['configs'] = []
  let loadError: string | null = null

  try {
    const result = await listFormatConfigs()
    configs = result.configs
  } catch (err) {
    loadError = err instanceof Error ? err.message : '加载失败'
  }

  return (
    <main className="page">
      <section className="hero">
        <p className="eyebrow">Format Configs</p>
        <h1>格式配置</h1>
        <p className="subtitle">管理论文排版规则，支持版本历史、Diff 对比与一键回滚。</p>
        <div className="buttonGroup">
          <Link className="button" href="/templates/upload">
            + 从模板反向学习
          </Link>
          <Link className="button buttonGhost" href="/">
            ← 返回首页
          </Link>
        </div>
      </section>

      {loadError ? (
        <div className="errorBox">{loadError}</div>
      ) : configs.length === 0 ? (
        <article className="card wide">
          <h2>暂无格式配置</h2>
          <p className="muted">上传 DOCX 模板以自动生成格式配置草稿。</p>
        </article>
      ) : (
        <section className="grid">
          <article className="card wide">
            <ul className="list">
              {configs.map((config) => (
                <li className="listItem" key={config.id}>
                  <div className="cardHeader">
                    <div className="cardTitleGroup">
                      <h3>{config.name}</h3>
                      <span className="muted small">
                        ID: {config.id} · v{config.currentVersionNumber} · {sourceLabel(config.source)}
                      </span>
                    </div>
                    <span className="badge accent">v{config.currentVersionNumber}</span>
                  </div>
                  <div className="buttonGroup" style= marginTop: '8px' >
                    <Link
                      className="button buttonGhost"
                      href={`/configs/${config.id}/versions`}
                    >
                      版本历史
                    </Link>
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