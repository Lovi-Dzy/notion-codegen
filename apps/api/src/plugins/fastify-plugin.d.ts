// Type augmentation so fastify-plugin works with ESM + NodeNext
declare module 'fastify-plugin' {
  import type { FastifyPluginAsync, FastifyPluginCallback } from 'fastify'
  function fp(
    plugin: FastifyPluginAsync | FastifyPluginCallback,
    opts?: { name?: string; fastify?: string; dependencies?: string[] },
  ): FastifyPluginAsync
  export = fp
}