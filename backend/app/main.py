import logging
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .analyzer import (
    clone_repo,
    analyze_repo,
    AnalyzerError,
    validate_github_url,
)
from .generator import generate_readme, GeneratorError


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


app = FastAPI(title="Reposcribe backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten this to your gateway's origin in production
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    repo_url: str


class GenerateRequest(BaseModel):
    repo_name: str
    file_count: int = 0
    tree: list[str] = []
    manifests: dict[str, str] = {}
    key_files: dict[str, str] = {}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest):
    total_start = time.perf_counter()

    try:
        # -------------------------
        # Validate URL
        # -------------------------
        start = time.perf_counter()

        repo_url = validate_github_url(req.repo_url)
        repo_name = repo_url.split("/")[-1]

        logger.info(
            "[%s] URL validation: %.3fs",
            repo_name,
            time.perf_counter() - start,
        )

        # -------------------------
        # Clone repository
        # -------------------------
        start = time.perf_counter()

        repo_dir = clone_repo(repo_url)

        clone_time = time.perf_counter() - start

        logger.info(
            "[%s] Clone completed: %.3fs",
            repo_name,
            clone_time,
        )

        # -------------------------
        # Analyze repository
        # -------------------------
        start = time.perf_counter()

        analysis = analyze_repo(repo_dir, repo_name)

        analyze_time = time.perf_counter() - start

        logger.info(
            "[%s] Analysis completed: %.3fs | files=%s",
            repo_name,
            analyze_time,
            analysis.get("file_count", "?"),
        )

        # -------------------------
        # Total
        # -------------------------
        total_time = time.perf_counter() - total_start

        logger.info(
            "[%s] TOTAL /api/analyze: %.3fs",
            repo_name,
            total_time,
        )

        return analysis

    except AnalyzerError as e:
        logger.exception("Analyzer error")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.exception("Unexpected analyze error")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/generate")
def generate(req: GenerateRequest):
    start = time.perf_counter()

    try:
        logger.info(
            "[%s] Starting README generation | files=%d | tree=%d | manifests=%d | key_files=%d",
            req.repo_name,
            req.file_count,
            len(req.tree),
            len(req.manifests),
            len(req.key_files),
        )

        readme = generate_readme(req.model_dump())

        elapsed = time.perf_counter() - start

        logger.info(
            "[%s] README generation completed: %.3fs | output_chars=%d",
            req.repo_name,
            elapsed,
            len(readme),
        )

        return {"readme_markdown": readme}

    except GeneratorError as e:
        logger.exception("Generator error")
        raise HTTPException(status_code=502, detail=str(e))

    except Exception as e:
        logger.exception("Unexpected generate error")
        raise HTTPException(status_code=500, detail="Internal server error")