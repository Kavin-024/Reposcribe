"""
Turns the bounded analysis payload into a README.md using Gemini.
Keeping this in its own module means swapping providers later
(Groq, OpenAI) only touches this file.
"""
import google.generativeai as genai

from .config import GEMINI_API_KEY, GEMINI_MODEL, MAX_PROMPT_CHARS


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


def _build_prompt(analysis: dict) -> str:
    parts = [f"Repository: {analysis.get('repo_name')}", ""]

    tree = analysis.get("tree", [])
    parts.append(f"File tree ({len(tree)} of {analysis.get('file_count', len(tree))} files shown):")
    parts.append("\n".join(tree[:400]))
    parts.append("")

    manifests = analysis.get("manifests", {})
    if manifests:
        parts.append("Manifest files:")
        for name, content in manifests.items():
            parts.append(f"--- {name} ---\n{content}")
        parts.append("")

    key_files = analysis.get("key_files", {})
    if key_files:
        parts.append("Key source files:")
        for name, content in key_files.items():
            parts.append(f"--- {name} ---\n{content}")

    parts.append("")
    parts.append("Write a README.md with these sections, in this order:")
    parts.append("\n".join(f"- {s}" for s in SECTIONS))
    parts.append("")
    parts.append("Output only the markdown, no commentary before or after.")

    prompt = "\n".join(parts)
    return prompt[:MAX_PROMPT_CHARS]


def generate_readme(analysis: dict) -> str:
    if not GEMINI_API_KEY:
        raise GeneratorError("GEMINI_API_KEY is not set on the backend.")

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_MODEL,
        system_instruction=SYSTEM_INSTRUCTION,
    )

    prompt = _build_prompt(analysis)
    try:
        response = model.generate_content(prompt)
    except Exception as e:  # noqa: BLE001 - surface upstream errors clearly
        raise GeneratorError(f"Gemini call failed: {e}")

    text = getattr(response, "text", None)
    if not text:
        raise GeneratorError("Gemini returned an empty response.")
    return text
