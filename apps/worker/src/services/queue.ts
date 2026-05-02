import { Worker, Queue } from 'bullmq'
import IORedis from 'ioredis'
import { env } from '../env.js'
import { processDocumentJob } from '../processors/document-jobs.js'

let _redis: IORedis | null = null

export function getRedisConnection(): IORedis {
  if (!_redis) {
    _redis = new IORedis(env.REDIS_URL, {
      maxRetriesPerRequest: null,
    })
  }
  return _redis
}

// Queue instance (for enqueueing from within Worker processors)
export const documentQueue = new Queue('document-processing', {
  connection: {
    host: new URL(env.REDIS_URL).hostname,
    port: parseInt(new URL(env.REDIS_URL).port || '6379', 10),
  },
})

let _worker: Worker | null = null

export function createDocumentWorker(): Worker {
  if (_worker) return _worker

  _worker = new Worker(
    'document-processing',
    async (job) => {
      return processDocumentJob(job)
    },
    {
      connection: getRedisConnection(),
      concurrency: env.WORKER_CONCURRENCY,
      removeOnComplete: { count: 100 },
      removeOnFail: { count: 500 },
    },
  )

  _worker.on('active', (job) => {
    console.log(`[Worker] Job active: ${job.name} #${job.id}`)
  })

  _worker.on('completed', (job, result) => {
    console.log(`[Worker] Job completed: ${job.name} #${job.id}`, result)
  })

  _worker.on('failed', (job, err) => {
    console.error(`[Worker] Job failed: ${job?.name} #${job?.id}`, err)
  })

  _worker.on('error', (err) => {
    console.error('[Worker] Worker error:', err)
  })

  return _worker
}

export async function closeWorker(): Promise<void> {
  await _worker?.close()
  await documentQueue.close()
  _redis?.disconnect()
  console.log('[Worker] Shutdown complete')
}