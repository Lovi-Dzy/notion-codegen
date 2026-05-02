import fp from 'fastify-plugin'
import type { FastifyPluginAsync } from 'fastify'
import { connectDb, disconnectDb } from '../services/db.js'
import { closeQueues } from '../services/queue.js'

/**
 * Fastify plugin that initialises and tears down shared services:
 * - Prisma (PostgreSQL)
 * - BullMQ / Redis queues
 *
 * Decorates the fastify instance with nothing — services are
 * imported directly via their singleton getters.
 */
const servicesPlugin: FastifyPluginAsync = async (fastify) => {
  await connectDb()

  fastify.addHook('onClose', async () => {
    await Promise.all([disconnectDb(), closeQueues()])
  })
}

export default fp(servicesPlugin, {
  name: 'services',
  fastify: '4.x',
})