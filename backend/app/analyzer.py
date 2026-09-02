"""
Clones a public GitHub repo into a temp dir, walks the tree, and extracts
a bounded amount of signal (file tree, manifest files, key source files)
so we never dump an entire codebase into the LLM prompt.
"""
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from .config import MAX_REPO_SIZE_MB, CLONE_TIMEOUT_SECONDS

GITHUB_URL_RE = re.compile(
    r"^https://github\.com/[\w.-]+/[\w.-]+/?$"
)

IGNORE_DIRS = {
    ".git", "node_modules", "venv", ".venv", "__pycache__", "dist", "build",
    ".next", "target", "vendor", ".idea", ".vscode", "coverage",
}
IGNORE_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2",
    ".ttf", ".eot", ".mp4", ".mp3", ".zip", ".tar", ".gz", ".pdf", ".lock",
}
MANIFEST_FILES = {
    "package.json", "requirements.txt", "pyproject.toml", "go.mod",
    "Cargo.toml", "pom.xml", "build.gradle", "Gemfile", "composer.json",
}
ENTRY_HINTS = {
    "main.py", "app.py", "index.js", "index.ts", "server.js", "main.go",
    "main.rs", "App.jsx", "App.tsx", "manage.py",
}

MAX_TREE_ENTRIES = 400
MAX_KEY_FILE_CHARS = 8000
MAX_TOTAL_KEY_CHARS = 40000


class AnalyzerError(Exception):
    pass


def validate_github_url(repo_url: str) -> str:
    repo_url = repo_url.strip().rstrip("/")
    if repo_url.endswith(".git"):
        repo_url = repo_url[: -len(".git")]
    if not GITHUB_URL_RE.match(repo_url):
        raise AnalyzerError(
            "Only public GitHub repo URLs are supported, e.g. "
            "https://github.com/owner/repo"
        )
    return repo_url


def clone_repo(repo_url: str) -> str:
    repo_url = validate_github_url(repo_url)
    dest = tempfile.mkdtemp(prefix="reposcribe_")
    try:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--single-branch", repo_url, dest],
            check=True,
            timeout=CLONE_TIMEOUT_SECONDS,
            capture_output=True,
        )
    except subprocess.TimeoutExpired:
        shutil.rmtree(dest, ignore_errors=True)
        raise AnalyzerError("Cloning the repo took too long and was aborted.")
    except subprocess.CalledProcessError as e:
        shutil.rmtree(dest, ignore_errors=True)
        stderr = e.stderr.decode(errors="ignore") if e.stderr else ""
        raise AnalyzerError(f"git clone failed: {stderr[:300] or 'unknown error'}")

    size_mb = _dir_size_mb(dest)
    if size_mb > MAX_REPO_SIZE_MB:
        shutil.rmtree(dest, ignore_errors=True)
        raise AnalyzerError(
            f"Repo is {size_mb:.1f} MB, over the {MAX_REPO_SIZE_MB} MB limit."
        )
    return dest


def _dir_size_mb(path: str) -> float:
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            fp = os.path.join(root, f)
            if os.path.isfile(fp):
                total += os.path.getsize(fp)
    return total / (1024 * 1024)


def analyze_repo(repo_dir: str, repo_name: str) -> dict:
    tree_lines = []
    manifests = {}
    key_files = {}
    total_key_chars = 0
    file_count = 0

    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS and not d.startswith(".")]
        rel_root = os.path.relpath(root, repo_dir)

        for fname in sorted(files):
            ext = Path(fname).suffix.lower()
            if ext in IGNORE_EXT:
                continue
            rel_path = fname if rel_root == "." else f"{rel_root}/{fname}"
            file_count += 1
            if len(tree_lines) < MAX_TREE_ENTRIES:
                tree_lines.append(rel_path)

            full_path = os.path.join(root, fname)

            if fname in MANIFEST_FILES and fname not in manifests:
                manifests[fname] = _read_capped(full_path, MAX_KEY_FILE_CHARS)

            elif fname in ENTRY_HINTS or fname.lower() == "readme.md":
                if total_key_chars < MAX_TOTAL_KEY_CHARS:
                    content = _read_capped(full_path, MAX_KEY_FILE_CHARS)
                    key_files[rel_path] = content
                    total_key_chars += len(content)

    try:
        shutil.rmtree(repo_dir, ignore_errors=True)
    except OSError:
        pass

    return {
        "repo_name": repo_name,
        "file_count": file_count,
        "tree": tree_lines,
        "manifests": manifests,
        "key_files": key_files,
    }


def _read_capped(path: str, max_chars: int) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read(max_chars)
    except OSError:
        return ""
