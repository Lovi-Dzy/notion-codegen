import {
  S3Client,
  PutObjectCommand,
  GetObjectCommand,
  DeleteObjectCommand,
  HeadObjectCommand,
} from '@aws-sdk/client-s3'
import { env } from '../env.js'

export const s3 = new S3Client({
  endpoint: env.S3_ENDPOINT,
  region: env.S3_REGION,
  credentials: {
    accessKeyId: env.S3_ACCESS_KEY,
    secretAccessKey: env.S3_SECRET_KEY,
  },
  forcePathStyle: env.S3_FORCE_PATH_STYLE,
})

const BUCKET = env.S3_BUCKET

/** Upload buffer to S3. Returns the key. */
export async function putObject(args: {
  key: string
  body: Buffer
  contentType: string
}): Promise<string> {
  await s3.send(
    new PutObjectCommand({
      Bucket: BUCKET,
      Key: args.key,
      Body: args.body,
      ContentType: args.contentType,
    }),
  )
  return args.key
}

/** Download S3 object as a Buffer. */
export async function getObjectBuffer(key: string): Promise<Buffer> {
  const response = await s3.send(
    new GetObjectCommand({ Bucket: BUCKET, Key: key }),
  )
  if (!response.Body) throw new Error(`S3 object not found: ${key}`)
  const bytes = await response.Body.transformToByteArray()
  return Buffer.from(bytes)
}

/** Download S3 object as UTF-8 string. */
export async function getObjectText(key: string): Promise<string> {
  const buf = await getObjectBuffer(key)
  return buf.toString('utf-8')
}

/** Delete an object. */
export async function deleteObject(key: string): Promise<void> {
  await s3.send(new DeleteObjectCommand({ Bucket: BUCKET, Key: key }))
}

/** Check whether an object exists. */
export async function objectExists(key: string): Promise<boolean> {
  try {
    await s3.send(new HeadObjectCommand({ Bucket: BUCKET, Key: key }))
    return true
  } catch {
    return false
  }
}