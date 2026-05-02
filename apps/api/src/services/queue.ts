import { Queue } from 'bullmq'
import IORedis from 'ioredis'
import { env } from '../env.js'
import type { DocumentJobData, JobName } from '@wfa/shared'

let redisConnection: IORedis | null = null

export function getRedisConnection(): IORedis {
  if (!redisConnection) {
    redisConnection = new IORedis(env.REDIS_URL, {
      maxRetriesPerRequest: null, // required by BullMQ
    })
  }
  return redisConnection
}

// ─── Document processing queue ────────────────────────────────────────────────
let _documentQueue: Queue<DocumentJobData> | null = null

export function getDocumentQueue(): Queue<DocumentJobData> {
  if (!_documentQueue) {
    _documentQueue = new Queue<DocumentJobData>('document-processing', {
      connection: getRedisConnection(),
      defaultJobOptions: {
        attempts: 3,
        backoff: { type: 'exponential', delay: 2000 },
        removeOnComplete: { count: 100 },
        removeOnFail: { count: 500 },
      },
    })
  }
  return _documentQueue
}

/** Enqueue a document processing job. Returns the created BullMQ Job. */
export async function enqueueDocumentJob(
  name: JobName,
  data: DocumentJobData,
  opts?: { priority?: number; delay?: number },
) {
  const queue = getDocumentQueue()
  return queue.add(name, data, opts)
}

/** Gracefully close all queue connections. */
export async function closeQueues(): Promise<void> {
  await _documentQueue?.close()
  redisConnection?.disconnect()
}