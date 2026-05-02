/**
 * 编辑器相关共享类型
 * Worker 阶段 9 定义了完整实现，这里仅提供公共导出类型。
 */

export type EditorBlockType =
  | 'title'
  | 'heading'
  | 'paragraph'
  | 'abstract'
  | 'keywords'
  | 'formula'
  | 'reference'
  | 'figureCaption'
  | 'tableCaption'
  | 'author'
  | 'acknowledgement'
  | 'appendix'
  | 'unknown'

export type EditorBlock = {
  id: string
  type: EditorBlockType
  text: string
  level?: number
  preserveText?: boolean
  confidence?: number
}

export type EditorLoadResponse = {
  document: {
    id: string
    status: string
    originalFileName?: string | null
  }
  blocks: EditorBlock[]
}

export type EditorSaveRequest = {
  blocks: EditorBlock[]
  changeNote?: string
}

export type EditorSaveResponse = {
  document: {
    id: string
    status: string
  }
  savedBlockCount: number
}