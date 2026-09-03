import os
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
MAX_REPO_SIZE_MB = int(os.getenv("MAX_REPO_SIZE_MB", "50"))
CLONE_TIMEOUT_SECONDS = int(os.getenv("CLONE_TIMEOUT_SECONDS", "30"))
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "60000"))
