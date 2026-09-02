import express from "express";
import cors from "cors";
import http from "http";
import { Server as SocketIOServer } from "socket.io";
import rateLimit from "express-rate-limit";
import { v4 as uuidv4 } from "uuid";
import "dotenv/config";

import { readmeQueue } from "./queue.js";

const app = express();
const server = http.createServer(app);
const io = new SocketIOServer(server, {
  cors: { origin: process.env.CORS_ORIGIN || "*" },
});

app.use(cors({ origin: process.env.CORS_ORIGIN || "*" }));
app.use(express.json());

const limiter = rateLimit({
  windowMs: Number(process.env.RATE_LIMIT_WINDOW_MS || 60000),
  max: Number(process.env.RATE_LIMIT_MAX || 10),
  standardHeaders: true,
  legacyHeaders: false,
  message: { error: "Too many requests. Please slow down and try again shortly." },
});

app.get("/health", (_req, res) => res.json({ status: "ok" }));

app.post("/api/jobs", limiter, async (req, res) => {
  const { repoUrl } = req.body || {};
  if (!repoUrl || typeof repoUrl !== "string") {
    return res.status(400).json({ error: "repoUrl is required." });
  }

  const jobId = uuidv4();
  await readmeQueue.add("generate-readme", { repoUrl, jobId }, { jobId });
  res.json({ jobId });
});

// Socket.IO: clients join a room named after their jobId to receive progress
io.on("connection", (socket) => {
  socket.on("subscribe", (jobId) => {
    if (typeof jobId === "string") socket.join(jobId);
  });
});

// Exported so the worker process (running separately) can emit to the same
// Socket.IO instance via Redis adapter in a multi-process setup. For local
// dev/single-process simplicity here, the worker publishes progress through
// Redis pub/sub, and this small bridge relays it to the room.
import { connection } from "./queue.js";
const sub = connection.duplicate();
sub.subscribe("job-events");
sub.on("message", (_channel, message) => {
  try {
    const evt = JSON.parse(message);
    io.to(evt.jobId).emit(evt.type, evt.payload);
  } catch {
    // ignore malformed events
  }
});

const PORT = process.env.PORT || 4000;
server.listen(PORT, () => console.log(`Gateway listening on :${PORT}`));
