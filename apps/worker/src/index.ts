import { connectDb, disconnectDb } from './services/db.js'
import { createDocumentWorker, closeWorker } from './services/queue.js'
import { env } from './env.js'

async function main(): Promise<void> {
  console.log(`📦 Starting WFA Worker (concurrency=${env.WORKER_CONCURRENCY}, env=${env.NODE_ENV})`)

  // 1. Connect to DB
  await connectDb()

  // 2. Start BullMQ Worker
  const worker = createDocumentWorker()

  console.log('🚀 Worker is running and listening for jobs on queue: document-processing')

  // 3. Graceful shutdown
  const shutdown = async (signal: string): Promise<void> => {
    console.log(`\n[Worker] Received ${signal}, shutting down gracefully...`)
    await closeWorker()
    await disconnectDb()
    process.exit(0)
  }

  process.on('SIGTERM', () => void shutdown('SIGTERM'))
  process.on('SIGINT', () => void shutdown('SIGINT'))

  // 4. Keep process alive
  process.on('uncaughtException', (err) => {
    console.error('[Worker] Uncaught exception:', err)
  })

  process.on('unhandledRejection', (reason) => {
    console.error('[Worker] Unhandled rejection:', reason)
  })
}

main().catch((err) => {
  console.error('[Worker] Failed to start:', err)
  process.exit(1)
})