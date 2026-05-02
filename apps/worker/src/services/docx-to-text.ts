/**
 * docx-to-text.ts
 * 使用 mammoth 将 DOCX Buffer 转换为 Markdown 文本
 * 供 Worker parse job 在源文件为 DOCX 时调用
 */
import mammoth from 'mammoth'

export type DocxToTextResult = {
  /** 提取的 Markdown 文本 */
  text: string
  /** mammoth 转换过程中的警告信息 */
  warnings: string[]
}

/**
 * 将 DOCX Buffer 转成 Markdown 文本。
 * 使用 mammoth 的默认样式映射，保留标题层级、加粗、斜体、列表等基础结构。
 */
export async function docxBufferToMarkdown(
  buffer: Buffer,
): Promise<DocxToTextResult> {
  const result = await mammoth.convertToMarkdown(
    { buffer },
    {
      styleMap: [
        "p[style-name='Heading 1'] => # ",
        "p[style-name='Heading 2'] => ## ",
        "p[style-name='Heading 3'] => ### ",
        "p[style-name='Heading 4'] => #### ",
        // 中文标题样式映射
        "p[style-name='\u6807\u9898 1'] => # ",
        "p[style-name='\u6807\u9898 2'] => ## ",
        "p[style-name='\u6807\u9898 3'] => ### ",
        "p[style-name='\u6807\u9898 4'] => #### ",
      ],
    },
  )

  const warnings = result.messages
    .filter((m) => m.type === 'warning')
    .map((m) => m.message)

  return {
    text: result.value,
    warnings,
  }
}

/**
 * 检测文件是否为 DOCX（根据 MIME 或文件名）
 */
export function isDocxFile(filename: string, mimeType: string): boolean {
  const lower = filename.toLowerCase()
  return (
    lower.endsWith('.docx') ||
    mimeType ===
      'application/vnd.openxmlformats-officedocument.wordprocessingml.document' ||
    mimeType === 'application/msword'
  )
}