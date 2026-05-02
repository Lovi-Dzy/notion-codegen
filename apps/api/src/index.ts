import Fastify from 'fastify'
import cors from '@fastify/cors'
import multipart from '@fastify/multipart'
import jwt from '@fastify/jwt'
import { env } from './env.js'
import servicesPlugin from './plugins/services.js'
import { healthRoutes } from './routes/health.js'
import { jobRoutes } from './routes/jobs.js'

// ─── Dynamically import route modules (may not exist yet in early stages) ─────
async function loadOptionalRoute(path: string) {
  try {
    const mod = await import(path)
    return mod.default ?? Object.values(mod)[0]
  } catch {
    return null
  }
}

async function buildApp() {
  const app = Fastify({
    logger: {
      level: env.NODE_ENV === 'production' ? 'info' : 'debug',
      transport:
        env.NODE_ENV !== 'production'
          ? { target: 'pino-pretty', options: { colorize: true } }
          : undefined,
    },
  })

  // ── Plugins ──────────────────────────────────────────────────────────────
  await app.register(cors, {
    origin: env.CORS_ORIGIN,
    credentials: true,
  })

  await app.register(multipart, {
    limits: { fileSize: 50 * 1024 * 1024 }, // 50 MB
  })

  await app.register(jwt, {
    secret: env.JWT_SECRET,
  })

  await app.register(servicesPlugin)

  // ── Core routes ──────────────────────────────────────────────────────────
  await app.register(healthRoutes)
  await app.register(jobRoutes, { prefix: '/api' })

  // ── Optional feature routes (added in later stages) ──────────────────────
  const optionalRoutes: Array<{ path: string; prefix: string }> = [
    { path: './routes/workspaces.js', prefix: '/api' },
    { path: './routes/documents.js', prefix: '/api' },
    { path: './routes/configs.js', prefix: '/api' },
    { path: './routes/templates.js', prefix: '/api' },
    { path: './routes/revisions.js', prefix: '/api' },
  ]

  for (const { path, prefix } of optionalRoutes) {
    const route = await loadOptionalRoute(path)
    if (route) await app.register(route, { prefix })
  }

  return app
}

async function main() {
  const app = await buildApp()

  try {
    await app.listen({ port: env.API_PORT, host: env.API_HOST })
    console.log(`🚀 API server running on http://${env.API_HOST}:${env.API_PORT}`)
  } catch (err) {
    app.log.error(err)
    process.exit(1)
  }

  // Graceful shutdown
  const shutdown = async (signal: string) => {
    console.log(`\nReceived ${signal}, shutting down...`)
    await app.close()
    process.exit(0)
  }

  process.on('SIGTERM', () => shutdown('SIGTERM'))
  process.on('SIGINT', () => shutdown('SIGINT'))
}

main()