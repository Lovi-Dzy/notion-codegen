/**
 * LLM Gateway — 统一的 LLM 调用接口
 *
 * 设计原则：
 * - 所有 Worker 内的 LLM 调用均通过此模块，不直接引用 openai SDK
 * - 支持运行时切换模型（从环境变量或调用方传入）
 * - 支持流式输出（streaming）和单次输出（completion）
 * - 内置重试逻辑（指数退避）
 */

export type LlmRole = 'system' | 'user' | 'assistant'

export type LlmMessage = {
  role: LlmRole
  content: string
}

export type LlmCompletionOptions = {
  /** Messages to send. */
  messages: LlmMessage[]
  /** Override model for this call. Falls back to DEFAULT_LLM_MODEL env. */
  model?: string
  /** Max output tokens. */
  maxTokens?: number
  /** Temperature (0-2). */
  temperature?: number
  /** Top-p. */
  topP?: number
  /** Stop sequences. */
  stop?: string[]
  /** If true, returns the raw stream instead of awaiting full content. */
  stream?: false
}

export type LlmStreamOptions = Omit<LlmCompletionOptions, 'stream'> & {
  stream: true
}

export type LlmCompletionResult = {
  content: string
  model: string
  promptTokens: number
  completionTokens: number
  totalTokens: number
  finishReason: string | null
}

export type LlmGatewayConfig = {
  apiKey: string
  baseUrl?: string
  defaultModel: string
  maxRetries?: number
  timeoutMs?: number
}

// ─── Runtime implementation — lazy-loaded to avoid top-level await ────────────────────

type OpenAIClient = {
  chat: {
    completions: {
      create: (args: unknown) => Promise<unknown>
    }
  }
}

let _client: OpenAIClient | null = null
let _config: LlmGatewayConfig | null = null

export function configureLlmGateway(config: LlmGatewayConfig): void {
  _config = config
  _client = null // reset so next call re-initialises
}

async function getClient(): Promise<{ client: OpenAIClient; config: LlmGatewayConfig }> {
  if (!_config) {
    // Auto-configure from environment if not explicitly set
    const apiKey = process.env.OPENAI_API_KEY ?? ''
    const baseUrl = process.env.OPENAI_BASE_URL
    const defaultModel = process.env.DEFAULT_LLM_MODEL ?? 'gpt-4o'

    if (!apiKey) {
      throw new Error(
        'LLM Gateway: OPENAI_API_KEY is not set. ' +
        'Call configureLlmGateway() or set the OPENAI_API_KEY environment variable.',
      )
    }

    _config = { apiKey, baseUrl, defaultModel }
  }

  if (!_client) {
    // Dynamic import to keep this file import-friendly in non-Node environments
    const { default: OpenAI } = await import('openai')
    _client = new OpenAI({
      apiKey: _config.apiKey,
      baseURL: _config.baseUrl,
      maxRetries: _config.maxRetries ?? 3,
      timeout: _config.timeoutMs ?? 60_000,
    }) as unknown as OpenAIClient
  }

  return { client: _client, config: _config }
}

/**
 * Single-shot completion — awaits the full response.
 */
export async function llmComplete(
  options: LlmCompletionOptions,
): Promise<LlmCompletionResult> {
  const { client, config } = await getClient()
  const model = options.model ?? config.defaultModel

  const response = await (client.chat.completions.create({
    model,
    messages: options.messages,
    max_tokens: options.maxTokens,
    temperature: options.temperature,
    top_p: options.topP,
    stop: options.stop,
    stream: false,
  }) as Promise<{
    choices: Array<{
      message: { content: string | null }
      finish_reason: string | null
    }>
    model: string
    usage: {
      prompt_tokens: number
      completion_tokens: number
      total_tokens: number
    } | null
  }>)

  const choice = response.choices[0]
  if (!choice) throw new Error('LLM Gateway: Empty response from API')

  return {
    content: choice.message.content ?? '',
    model: response.model,
    promptTokens: response.usage?.prompt_tokens ?? 0,
    completionTokens: response.usage?.completion_tokens ?? 0,
    totalTokens: response.usage?.total_tokens ?? 0,
    finishReason: choice.finish_reason,
  }
}

/**
 * Streaming completion — returns an async iterable of text chunks.
 */
export async function* llmStream(
  options: LlmStreamOptions,
): AsyncGenerator<string, void, undefined> {
  const { client, config } = await getClient()
  const model = options.model ?? config.defaultModel

  const stream = await (client.chat.completions.create({
    model,
    messages: options.messages,
    max_tokens: options.maxTokens,
    temperature: options.temperature,
    top_p: options.topP,
    stop: options.stop,
    stream: true,
  }) as Promise<AsyncIterable<{
    choices: Array<{
      delta: { content?: string | null }
    }>
  }>>
  )

  for await (const chunk of stream) {
    const delta = chunk.choices[0]?.delta?.content
    if (delta) yield delta
  }
}

/**
 * One-shot JSON completion — parses and returns typed JSON.
 * Throws if the response is not valid JSON.
 */
export async function llmCompleteJson<T = unknown>(
  options: LlmCompletionOptions & { schema?: string },
): Promise<T> {
  const systemMessages: LlmMessage[] = [
    {
      role: 'system',
      content:
        options.schema
          ? `You must respond with valid JSON that matches this schema:\n${options.schema}`
          : 'You must respond with valid JSON only. Do not add markdown code fences.',
    },
  ]

  const allMessages: LlmMessage[] = [
    ...systemMessages,
    ...options.messages.filter((m) => m.role !== 'system'),
  ]

  const result = await llmComplete({ ...options, messages: allMessages })

  // Strip markdown code fences if present
  const cleaned = result.content
    .replace(/^```(?:json)?\s*/i, '')
    .replace(/\s*```\s*$/, '')
    .trim()

  try {
    return JSON.parse(cleaned) as T
  } catch {
    throw new Error(
      `LLM Gateway: Failed to parse JSON response.\nRaw content:\n${result.content}`,
    )
  }
}