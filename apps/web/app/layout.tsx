import type { Metadata } from 'next'
import Link from 'next/link'
import './globals.css'

export const metadata: Metadata = {
  title: 'Word Format Agent',
  description: '论文格式自动化平台',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body>
        <header className="topbar">
          <Link className="brand" href="/">
            <span className="brandIcon">📄</span>
            Word Format Agent
          </Link>
          <nav className="nav">
            <Link href="/documents">文档</Link>
            <Link href="/documents/upload">上传</Link>
            <Link href="/configs">格式配置</Link>
            <Link href="/templates/upload">模板分析</Link>
          </nav>
        </header>
        {children}
        <footer className="footer">
          <span>Word Format Agent</span>
          <span>·</span>
          <span>Fastify + Prisma + BullMQ + Next.js</span>
        </footer>
      </body>
    </html>
  )
}