import { Worker } from "bullmq";
import axios from "axios";
import "dotenv/config";

import { connection } from "./queue.js";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const publisher = connection.duplicate();

function publish(jobId, type, payload) {
  publisher.publish(
    "job-events",
    JSON.stringify({ jobId, type, payload })
  );
}

function elapsed(start) {
  return `${Date.now() - start}ms`;
}

new Worker(
  "readme-jobs",
  async (job) => {
    const jobStart = Date.now();
    const { repoUrl, jobId } = job.data;

    console.log(`[${jobId}] Job started`);

    // -------------------------
    // 1. Clone + analyze
    // -------------------------
    const analyzeStart = Date.now();

    publish(jobId, "status", {
      step: "cloning",
      message: `Cloning ${repoUrl}...`,
    });

    const { data: analysis } = await axios.post(
      `${BACKEND_URL}/api/analyze`,
      {
        repo_url: repoUrl,
      },
      {
        timeout: 45000,
      }
    );

    console.log(
      `[${jobId}] Analyze completed in ${elapsed(analyzeStart)}`
    );

    publish(jobId, "status", {
      step: "analyzed",
      message: `Analyzed ${analysis.file_count} files. Generating docs...`,
    });

    // -------------------------
    // 2. Gemini
    // -------------------------
    const generateStart = Date.now();

    const { data: gen } = await axios.post(
      `${BACKEND_URL}/api/generate`,
      analysis,
      {
        timeout: 60000,
      }
    );

    console.log(
      `[${jobId}] Gemini generation completed in ${elapsed(generateStart)}`
    );

    // -------------------------
    // 3. Complete
    // -------------------------
    console.log(
      `[${jobId}] Total job time: ${elapsed(jobStart)}`
    );

    publish(jobId, "done", {
      readme: gen.readme_markdown,
      repoName: analysis.repo_name,
    });

    return {
      ok: true,
      analyzeMs: Date.now() - analyzeStart,
      totalMs: Date.now() - jobStart,
    };
  },
  {
    connection,
    concurrency: 2,
  }
).on("failed", (job, err) => {
  const jobId = job?.data?.jobId;
  const detail =
    err?.response?.data?.detail || err.message;

  console.error(`[${jobId}] Job failed:`, detail);

  if (jobId) {
    publish(jobId, "error", {
      message: detail,
    });
  }
});

console.log("Worker listening for readme-jobs...");