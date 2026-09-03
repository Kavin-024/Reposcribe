"""
Turns the bounded analysis payload into a README.md using Gemini.

Keeping this in its own module means swapping providers later
(Groq, OpenAI) only touches this file.
"""

import logging
import time

import google.generativeai as genai

from .config import GEMINI_API_KEY, GEMINI_MODEL, MAX_PROMPT_CHARS


logger = logging.getLogger(__name__)


class GeneratorError(Exception):
    pass


SYSTEM_INSTRUCTION = (
    "You are a senior engineer writing a README for a GitHub repo. "
    "Write clear, accurate, sentence-case markdown. Do not invent features, "
    "commands, or file names that are not evidenced in the provided context. "
    "If something is unclear, describe it generally rather than guessing specifics."
)


SECTIONS = [
    "Project title and one-line description",
    "Overview (2-4 sentences on what it does and why it's useful)",
    "Features (bullet list, only what's evidenced)",
    "Tech stack (inferred from manifests/imports)",
    "Project structure (short, based on the file tree)",
    "Installation",
    "Usage",
    "License (say 'Not specified' if no LICENSE file was seen)",
]


# Configure Gemini once when the module is imported.
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_INSTRUCTION,
    )
else:
    model = None


def _build_prompt(analysis: dict) -> str:
    parts = [
        f"Repository: {analysis.get('repo_name')}",
        "",
    ]

    # -------------------------
    # File tree
    # -------------------------
    tree = analysis.get("tree", [])

    parts.append(
        f"File tree ({len(tree)} of "
        f"{analysis.get('file_count', len(tree))} files shown):"
    )

    parts.append("\n".join(tree[:300]))
    parts.append("")

    # -------------------------
    # Manifest files
    # -------------------------
    manifests = analysis.get("manifests", {})

    if manifests:
        parts.append("Manifest files:")

        for name, content in manifests.items():
            parts.append(
                f"--- {name} ---\n{content}"
            )

        parts.append("")

    # -------------------------
    # Key source files
    # -------------------------
    key_files = analysis.get("key_files", {})

    if key_files:
        parts.append("Key source files:")

        for name, content in key_files.items():
            parts.append(
                f"--- {name} ---\n{content}"
            )

        parts.append("")

    # -------------------------
    # README instructions
    # -------------------------
    parts.append(
        "Write a README.md with these sections, in this order:"
    )

    parts.append(
        "\n".join(f"- {section}" for section in SECTIONS)
    )

    parts.append("")
    parts.append(
        "Output only the markdown, no commentary before or after."
    )

    prompt = "\n".join(parts)

    # Enforce the configured maximum.
    if len(prompt) > MAX_PROMPT_CHARS:
        logger.warning(
            "Prompt truncated from %d to %d characters",
            len(prompt),
            MAX_PROMPT_CHARS,
        )

    return prompt[:MAX_PROMPT_CHARS]


def generate_readme(analysis: dict) -> str:
    if not GEMINI_API_KEY:
        raise GeneratorError(
            "GEMINI_API_KEY is not set on the backend."
        )

    if model is None:
        raise GeneratorError(
            "Gemini model is not initialized."
        )

    # -------------------------
    # Build prompt
    # -------------------------
    prompt_start = time.perf_counter()

    prompt = _build_prompt(analysis)

    prompt_build_time = time.perf_counter() - prompt_start

    logger.info(
        "[%s] Prompt built in %.3fs | chars=%d",
        analysis.get("repo_name"),
        prompt_build_time,
        len(prompt),
    )

    # -------------------------
    # Gemini request
    # -------------------------
    gemini_start = time.perf_counter()

    try:
        response = model.generate_content(prompt)

    except Exception as e:
        elapsed = time.perf_counter() - gemini_start

        logger.exception(
            "[%s] Gemini failed after %.3fs",
            analysis.get("repo_name"),
            elapsed,
        )

        raise GeneratorError(
            f"Gemini call failed: {e}"
        )

    gemini_time = time.perf_counter() - gemini_start

    logger.info(
        "[%s] Gemini response received in %.3fs",
        analysis.get("repo_name"),
        gemini_time,
    )

    # -------------------------
    # Extract response
    # -------------------------
    text = getattr(response, "text", None)

    if not text:
        raise GeneratorError(
            "Gemini returned an empty response."
        )

    logger.info(
        "[%s] README generated | output_chars=%d",
        analysis.get("repo_name"),
        len(text),
    )

    return text