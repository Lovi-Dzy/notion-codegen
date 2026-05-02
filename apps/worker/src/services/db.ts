import { PrismaClient } from '@prisma/client'

let _prisma: PrismaClient | null = null

export function getPrisma(): PrismaClient {
  if (!_prisma) {
    _prisma = new PrismaClient({
      log:
        process.env.NODE_ENV === 'development'
          ? ['error', 'warn']
          : ['error'],
    })
  }
  return _prisma
}

/** Shorthand singleton export — used by processors directly */
export const prisma = new PrismaClient({
  log: process.env.NODE_ENV === 'development' ? ['error', 'warn'] : ['error'],
})

export async function connectDb(): Promise<void> {
  await prisma.$connect()
  console.log('✅ Worker: Database connected')
}

export async function disconnectDb(): Promise<void> {
  await prisma.$disconnect()
  console.log('Worker: Database disconnected')
}