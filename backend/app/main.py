from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .analyzer import clone_repo, analyze_repo, AnalyzerError, validate_github_url
from .generator import generate_readme, GeneratorError

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
    try:
        repo_url = validate_github_url(req.repo_url)
        repo_name = repo_url.split("/")[-1]
        repo_dir = clone_repo(repo_url)
        analysis = analyze_repo(repo_dir, repo_name)
        return analysis
    except AnalyzerError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/generate")
def generate(req: GenerateRequest):
    try:
        readme = generate_readme(req.model_dump())
        return {"readme_markdown": readme}
    except GeneratorError as e:
        raise HTTPException(status_code=502, detail=str(e))
