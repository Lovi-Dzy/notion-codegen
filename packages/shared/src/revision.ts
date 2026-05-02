/**
 * 修订相关共享类型
 * Worker 阶段 8 定义了完整实现，这里仅提供公共导出类型。
 */

export type RevisionPatchKind =
  | 'config_change'
  | 'ast_change'
  | 'config_and_ast_change'
  | 'no_op'

export type RevisionPatchOperation = {
  type: 'set_block_type' | 'set_heading_level' | 'set_config_value' | 'insert_block' | 'remove_block'
  target?: string
  value?: unknown
  path?: string
  blockId?: string
}

export type RevisionPatch = {
  kind: RevisionPatchKind
  summary: string
  operations: RevisionPatchOperation[]
}

export type RevisionResult = {
  ast: unknown
  changed: boolean
  warnings: string[]
}

export type ReviseDocumentRequest = {
  instruction: string
}

export type ReviseDocumentResponse = {
  document: {
    id: string
    status: string
  }
  reviseJob: {
    jobId: string
    queueName: string
    status: string
  }
}