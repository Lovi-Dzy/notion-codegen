import type { FastifyPluginAsync } from 'fastify'
import { z } from 'zod'
import { getDocumentQueue } from '../services/queue.js'

const jobIdSchema = z.object({ jobId: z.string().min(1) })

export const jobRoutes: FastifyPluginAsync = async (fastify) => {
  /** GET /jobs/:jobId — poll job status & progress */
  fastify.get<{ Params: { jobId: string } }>(
    '/jobs/:jobId',
    {
      schema: {
        tags: ['jobs'],
        params: {
          type: 'object',
          properties: { jobId: { type: 'string' } },
          required: ['jobId'],
        },
        response: {
          200: {
            type: 'object',
            properties: {
              jobId: { type: 'string' },
              name: { type: 'string' },
              state: { type: 'string' },
              progress: {},
              returnValue: {},
              failedReason: { type: 'string', nullable: true },
              createdAt: { type: 'number', nullable: true },
              processedAt: { type: 'number', nullable: true },
              finishedAt: { type: 'number', nullable: true },
            },
          },
        },
      },
    },
    async (req, reply) => {
      const { jobId } = jobIdSchema.parse(req.params)
      const queue = getDocumentQueue()
      const job = await queue.getJob(jobId)

      if (!job) {
        return reply.status(404).send({ error: 'Job not found', jobId })
      }

      const state = await job.getState()

      return reply.send({
        jobId: job.id,
        name: job.name,
        state,
        progress: job.progress,
        returnValue: job.returnvalue ?? null,
        failedReason: job.failedReason ?? null,
        createdAt: job.timestamp ?? null,
        processedAt: job.processedOn ?? null,
        finishedAt: job.finishedOn ?? null,
      })
    },
  )

  /** DELETE /jobs/:jobId — cancel / remove a pending job */
  fastify.delete<{ Params: { jobId: string } }>(
    '/jobs/:jobId',
    {
      schema: {
        tags: ['jobs'],
        params: {
          type: 'object',
          properties: { jobId: { type: 'string' } },
          required: ['jobId'],
        },
      },
    },
    async (req, reply) => {
      const { jobId } = jobIdSchema.parse(req.params)
      const queue = getDocumentQueue()
      const job = await queue.getJob(jobId)

      if (!job) {
        return reply.status(404).send({ error: 'Job not found', jobId })
      }

      await job.remove()
      return reply.send({ success: true, jobId })
    },
  )
}