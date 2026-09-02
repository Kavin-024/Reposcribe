# Reposcribe

Paste a public GitHub repo URL, get a generated README based on the actual
code (file structure, manifests, entry points) — not a generic template.

## Architecture

Browser → Nginx (reverse proxy, rate limiting) → React (static) + Node.js
gateway (job queue via BullMQ/Redis, Socket.IO progress) → FastAPI backend
(clones the repo, extracts a bounded set of signal, calls Gemini) → back to
the browser as a live-updating markdown preview.

## Prerequisites

- Python 3.11+
- Node.js 20+
- Redis (or Docker, to run it in a container)
- A Gemini API key: https://aistudio.google.com/apikey
- `git` installed and on PATH (the backend shells out to it)

## 1. Configure environment variables

```bash
cp backend/.env.example backend/.env
cp gateway/.env.example gateway/.env
```

Edit `backend/.env` and set `GEMINI_API_KEY`.

## 2. Run locally without Docker (fastest for development)

Open four terminals:

```bash
# Terminal 1 — Redis
redis-server

# Terminal 2 — backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# Terminal 3 — gateway (API + WebSocket) and worker
cd gateway
npm install
npm run dev   # runs server.js and worker.js together

# Terminal 4 — frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 — Vite's dev proxy forwards `/api` and
`/socket.io` to the gateway on port 4000, so you don't need Nginx for this
step.

Try it on a small public repo first (your own repos are a good test —
`https://github.com/kavin-024/api-mock-server`).

## 3. Run the full stack with Docker Compose (matches production)

This is the step that actually validates what you'll deploy to EC2 —
Nginx in front, rate limiting active, everything talking over the Docker
network instead of localhost.

```bash
docker compose up --build
```

Open http://localhost:8080 (Nginx's port). Check things work end to end,
then deliberately test the guardrails:

- Paste a non-GitHub URL → should get a clear 400, not a crash.
- Paste a huge public repo → should hit the size limit cleanly.
- Fire off 15 requests quickly → should start getting rate-limited (both
  at the gateway and at Nginx).

## 4. Logs and debugging

```bash
docker compose logs -f backend
docker compose logs -f gateway
```

## Next steps (not included here)

- Deploy this same `docker-compose.yml` to an EC2 instance, put a real
  domain in front with Certbot for SSL, and lock the security group to
  22/80/443.
- Swap `GEMINI_MODEL` in `backend/.env` to compare output quality/speed
  against other Flash variants.
- Add the monitoring project on top once this is live, watching this
  service's own `/health` endpoints.
