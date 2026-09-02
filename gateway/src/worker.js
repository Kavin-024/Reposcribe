import { Worker } from "bullmq";
import axios from "axios";
import "dotenv/config";

import { connection } from "./queue.js";

const BACKEND_URL = process.env.BACKEND_URL || "http://localhost:8000";
const publisher = connection.duplicate();

function publish(jobId, type, payload) {
  publisher.publish("job-events", JSON.stringify({ jobId, type, payload }));
}

new Worker(
  "readme-jobs",
  async (job) => {
    const { repoUrl, jobId } = job.data;

    publish(jobId, "status", { step: "cloning", message: `Cloning ${repoUrl}...` });
    const { data: analysis } = await axios.post(`${BACKEND_URL}/api/analyze`, {
      repo_url: repoUrl,
    });

    publish(jobId, "status", {
      step: "analyzed",
      message: `Analyzed ${analysis.file_count} files. Generating docs...`,
    });

    const { data: gen } = await axios.post(`${BACKEND_URL}/api/generate`, analysis);

    publish(jobId, "done", { readme: gen.readme_markdown, repoName: analysis.repo_name });
    return { ok: true };
  },
  { connection }
).on("failed", (job, err) => {
  const jobId = job?.data?.jobId;
  const detail = err?.response?.data?.detail || err.message;
  if (jobId) publish(jobId, "error", { message: detail });
});

console.log("Worker listening for readme-jobs...");
