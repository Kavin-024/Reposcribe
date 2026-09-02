import { Queue } from "bullmq";
import IORedis from "ioredis";
import "dotenv/config";

export const connection = new IORedis(
  process.env.REDIS_URL || "redis://localhost:6379",
  { maxRetriesPerRequest: null }
);

export const readmeQueue = new Queue("readme-jobs", { connection });
