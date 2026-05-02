import type { FastifyPluginAsync } from 'fastify'
import { prisma } from '../services/db.js'
import { getRedisConnection } from '../services/queue.js'

export const healthRoutes: FastifyPluginAsync = async (fastify) => {
  fastify.get(
    '/health',
    {
      schema: {
        tags: ['system'],
        summary: 'Health check',
        response: {
          200: {
            type: 'object',
            properties: {
              status: { type: 'string' },
              db: { type: 'string' },
              redis: { type: 'string' },
              timestamp: { type: 'string' },
            },
          },
        },
      },
    },
    async (_req, reply) => {
      let dbStatus = 'ok'
      let redisStatus = 'ok'

      try {
        await prisma.$queryRaw`SELECT 1`
      } catch {
        dbStatus = 'error'
      }

      try {
        await getRedisConnection().ping()
      } catch {
        redisStatus = 'error'
      }

      const overallOk = dbStatus === 'ok' && redisStatus === 'ok'
      return reply.status(overallOk ? 200 : 503).send({
        status: overallOk ? 'ok' : 'degraded',
        db: dbStatus,
        redis: redisStatus,
        timestamp: new Date().toISOString(),
      })
    },
  )
}