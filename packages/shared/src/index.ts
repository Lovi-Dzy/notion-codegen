/**
 * @wfa/shared — 共享类型与工具包
 *
 * 主入口：导出所有公共 API 类型、工具函数、常量。
 * 子路径导入（如 @wfa/shared/template）由 package.json exports 字段定义。
 */

// 核心类型
export * from './types.js'

// 修订相关
export * from './revision.js'

// 编辑器相关
export * from './editor.js'

// LLM Gateway
export * from './llm-gateway.js'

// 模板分析
// 注：template.ts 也可通过 @wfa/shared/template 子路径导入
export * from './template.js'