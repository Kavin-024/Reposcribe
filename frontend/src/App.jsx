import { useRef, useState } from "react";
import { io } from "socket.io-client";
import ReactMarkdown from "react-markdown";
import "./App.css";

const STEPS = [
  { key: "cloning", label: "Cloning repository" },
  { key: "analyzed", label: "Analyzing structure" },
  { key: "done", label: "Generating README" },
];

export default function App() {
  const [repoUrl, setRepoUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [events, setEvents] = useState([]);
  const [readme, setReadme] = useState("");
  const [repoName, setRepoName] = useState("");
  const socketRef = useRef(null);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setReadme("");
    setEvents([]);
    setSubmitting(true);

    try {
      const res = await fetch("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ repoUrl }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || "Could not start the job.");

      const socket = io({ path: "/socket.io" });
      socketRef.current = socket;
      socket.emit("subscribe", data.jobId);

      socket.on("status", (payload) => {
        setEvents((prev) => [...prev, { type: "status", ...payload }]);
      });

      socket.on("done", (payload) => {
        setEvents((prev) => [...prev, { type: "status", step: "done", message: "README ready" }]);
        setReadme(payload.readme);
        setRepoName(payload.repoName);
        setSubmitting(false);
        socket.disconnect();
      });

      socket.on("error", (payload) => {
        setError(payload.message || "Something went wrong.");
        setSubmitting(false);
        socket.disconnect();
      });
    } catch (err) {
      setError(err.message);
      setSubmitting(false);
    }
  }

  function handleCopy() {
    navigator.clipboard.writeText(readme);
  }

  function handleDownload() {
    const blob = new Blob([readme], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "README.md";
    a.click();
    URL.revokeObjectURL(url);
  }

  const currentStepIndex = events.length
    ? STEPS.findIndex((s) => s.key === events[events.length - 1].step)
    : -1;

  return (
    <div className="shell">
      <div className="topline">
        <h1>Reposcribe</h1>
        <p>Paste a public GitHub repo URL and get a README, generated from the actual code.</p>
      </div>

      <div className="workbench">
        <div className="pane">
          <h2>Generate</h2>
          <form className="url-form" onSubmit={handleSubmit}>
            <input
              type="url"
              placeholder="https://github.com/owner/repo"
              value={repoUrl}
              onChange={(e) => setRepoUrl(e.target.value)}
              required
            />
            <button type="submit" disabled={submitting}>
              {submitting ? "Working..." : "Generate"}
            </button>
          </form>

          {error && <div className="error">{error}</div>}

          <div className="log">
            {STEPS.map((step, i) => (
              <div
                key={step.key}
                className={`row ${i <= currentStepIndex ? "done" : "pending"}`}
              >
                <span className="dot">{i <= currentStepIndex ? "\u25CF" : "\u25CB"}</span>
                <span>{step.label}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="pane preview">
          <h2>{repoName ? `README — ${repoName}` : "Preview"}</h2>
          {readme ? (
            <>
              <div className="preview-actions">
                <button onClick={handleCopy}>Copy markdown</button>
                <button onClick={handleDownload}>Download README.md</button>
              </div>
              <div className="markdown-body">
                <ReactMarkdown>{readme}</ReactMarkdown>
              </div>
            </>
          ) : (
            <div className="preview-empty">Your generated README will appear here.</div>
          )}
        </div>
      </div>
    </div>
  );
}
