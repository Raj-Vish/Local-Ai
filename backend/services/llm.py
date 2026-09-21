"""Stage 7: the single door to the language model.

Nothing else in this backend knows that the model is Qwen, or that it is
served by Ollama, or where it lives. Everything goes through generate()
below. That is the same idea as the frontend's client.js: one door, so the
thing on the other side can change without touching anything else.

NOTHING IS INSTALLED ON THIS MACHINE FOR THIS.
The model runs on a teammate's machine and is reached over HTTP. This module
is a client, not a runtime. Until LLM_URL is set in .env, available() is
False and callers get a clear message rather than a stack trace.

The rule this module exists to enforce
--------------------------------------
    THE DATABASE CALCULATES. THE MODEL ONLY PHRASES.

A figure is never asked of the model. Totals are computed by MySQL and passed
in as facts; retrieved document text is passed in as context; the model is
asked to write the sentence around them. The prompt says so explicitly, and
callers pass figures through `facts` rather than hoping the model adds up the
context correctly. It cannot be trusted to, and it does not need to be.
"""
import logging

import requests

from config import settings

log = logging.getLogger("uvicorn.error")

# Sent with every request. Deliberately blunt: a small model needs the rule
# stated plainly and repeated, not implied.
SYSTEM_RULES = """You are a careful assistant inside a company expense system.

Rules you must follow:
1. Use ONLY the FACTS and CONTEXT provided below. If they do not answer the
   question, say you do not have that information.
2. NEVER calculate, add, total or estimate any amount. Every figure you state
   must be copied exactly from FACTS or CONTEXT. If a total is not given to
   you, say it is not available -- do not work it out.
3. Do not invent vendors, dates, amounts or documents.
4. Answer in two or three sentences, plainly."""


class LLMUnavailable(Exception):
    """The language service is not configured or cannot be reached."""


def is_configured() -> bool:
    """Whether a language service address has been set."""
    return bool(settings.LLM_URL.strip())


def available() -> tuple[bool, str]:
    """(reachable, explanation). Never raises, so a health check can call it."""
    if not is_configured():
        return False, "No language service is configured (LLM_URL is not set)."
    try:
        response = requests.get(f"{settings.LLM_URL.rstrip('/')}/api/tags", timeout=4)
        if response.status_code == 200:
            return True, f"Connected to {settings.LLM_MODEL}."
        return False, f"Language service answered HTTP {response.status_code}."
    except requests.RequestException as exc:
        return False, f"Cannot reach the language service ({type(exc).__name__})."


def build_prompt(question: str, context: list[str], facts: list[str] | None = None) -> str:
    """Assemble what the model is shown. Kept separate so it can be tested."""
    parts = [SYSTEM_RULES, ""]

    if facts:
        parts.append("FACTS (computed by the database -- these figures are correct,")
        parts.append("copy them exactly, never recompute them):")
        parts.extend(f"- {f}" for f in facts)
        parts.append("")

    if context:
        parts.append("CONTEXT (extracts from the user's own documents):")
        for position, chunk in enumerate(context, start=1):
            parts.append(f"[{position}] {chunk}")
        parts.append("")

    parts.append(f"QUESTION: {question}")
    parts.append("ANSWER:")
    return "\n".join(parts)


def generate(question: str, context: list[str], facts: list[str] | None = None) -> str:
    """Ask the language service to phrase an answer. Returns its text.

    Raises LLMUnavailable if it is not configured or does not answer; callers
    should treat that as "retrieval still worked, phrasing did not".
    """
    if not is_configured():
        raise LLMUnavailable(
            "No language service is configured. Set LLM_URL in .env to the "
            "address of the machine running Ollama."
        )

    prompt = build_prompt(question, context, facts)
    url = f"{settings.LLM_URL.rstrip('/')}/api/generate"

    try:
        response = requests.post(
            url,
            json={
                "model": settings.LLM_MODEL,
                "prompt": prompt,
                "stream": False,
                # Low temperature: this job is faithful phrasing of supplied
                # figures, not invention.
                "options": {"temperature": 0.2},
            },
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
    except requests.Timeout:
        raise LLMUnavailable(
            f"The language service did not answer within {settings.LLM_TIMEOUT_SECONDS}s."
        )
    except requests.RequestException as exc:
        raise LLMUnavailable(f"Cannot reach the language service ({type(exc).__name__}).")

    if response.status_code != 200:
        raise LLMUnavailable(f"The language service answered HTTP {response.status_code}.")

    try:
        body = response.json()
    except ValueError:
        raise LLMUnavailable("The language service returned something that was not JSON.")

    # Ollama's /api/generate returns {"response": "...", "done": true, ...}.
    # Read defensively: the contract belongs to the other team.
    answer = (body.get("response") or "").strip()
    if not answer:
        raise LLMUnavailable("The language service returned an empty answer.")
    return answer
