"""
ghoul/specialist.py — Specialist coding-agent personas.

Each specialist is a preconfigured Claude persona with a specific system
prompt tailored to a particular area of expertise (e.g. algorithms,
security, testing, architecture).  The :func:`run_specialist` function
sends a task through a specialist persona and returns the response.
"""

import anthropic

from ghoul.config import CFG


# ---------------------------------------------------------------------------
# Specialist definitions
# ---------------------------------------------------------------------------

SPECIALISTS: dict[str, dict] = {
    "architect": {
        "name": "Architect",
        "system": (
            "You are a senior software architect. You focus on high-level design, "
            "module boundaries, dependency management, and clean abstractions. "
            "When given code, suggest structural improvements and design patterns. "
            "Return ONLY the improved Python code — no markdown fences, no explanations."
        ),
    },
    "algorithms": {
        "name": "Algorithms Expert",
        "system": (
            "You are an algorithms and data-structures expert. You focus on "
            "computational complexity, choosing the right data structures, "
            "optimizing hot paths, and reducing time/space complexity. "
            "Return ONLY the improved Python code — no markdown fences, no explanations."
        ),
    },
    "security": {
        "name": "Security Specialist",
        "system": (
            "You are a cybersecurity and secure-coding specialist. You focus on "
            "input validation, injection prevention, secrets handling, sandboxing "
            "considerations, and safe subprocess management. "
            "Return ONLY the improved Python code — no markdown fences, no explanations."
        ),
    },
    "testing": {
        "name": "Testing & QA Specialist",
        "system": (
            "You are a testing and quality-assurance specialist. You focus on "
            "edge cases, error handling, defensive programming, logging, and "
            "adding appropriate assertions and validation. "
            "Return ONLY the improved Python code — no markdown fences, no explanations."
        ),
    },
    "performance": {
        "name": "Performance Engineer",
        "system": (
            "You are a performance engineer. You focus on runtime efficiency, "
            "memory usage, I/O optimization, caching strategies, and profiling. "
            "Return ONLY the improved Python code — no markdown fences, no explanations."
        ),
    },
    "readability": {
        "name": "Readability Reviewer",
        "system": (
            "You are a code readability reviewer. You focus on naming conventions, "
            "docstrings, comments, code organization, PEP 8 compliance, and making "
            "the code as clear and maintainable as possible. "
            "Return ONLY the improved Python code — no markdown fences, no explanations."
        ),
    },
}


def list_specialists() -> list[str]:
    """Return the names of all available specialist personas."""
    return list(SPECIALISTS.keys())


def run_specialist(
    specialist_id: str,
    code: str,
    task: str | None = None,
    extra_instructions: str | None = None,
) -> str:
    """
    Run a specialist persona on *code*.

    Parameters
    ----------
    specialist_id:      Key in :data:`SPECIALISTS` (e.g. ``"architect"``).
    code:               The source code to review / improve.
    task:               Optional task context.
    extra_instructions: Optional additional instructions.

    Returns
    -------
    The specialist's response text (improved code or suggestions).
    """
    if specialist_id not in SPECIALISTS:
        raise ValueError(
            f"Unknown specialist '{specialist_id}'. "
            f"Available: {list_specialists()}"
        )

    spec = SPECIALISTS[specialist_id]
    client = anthropic.Anthropic(api_key=CFG["anthropic_api_key"])

    prompt_parts = []
    if task:
        prompt_parts.append(f"Context / task: {task}")
    prompt_parts.append(f"Source code:\n\n```python\n{code}\n```")
    if extra_instructions:
        prompt_parts.append(f"\nAdditional instructions:\n{extra_instructions}")
    prompt_parts.append(
        "\nPlease improve this code according to your area of expertise. "
        "Return ONLY the improved Python source code."
    )

    message = client.messages.create(
        model=CFG["model"],
        max_tokens=8192,
        system=spec["system"],
        messages=[{"role": "user", "content": "\n\n".join(prompt_parts)}],
    )

    response_text = message.content[0].text.strip()

    # Strip accidental markdown fences
    if response_text.startswith("```"):
        lines = response_text.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        response_text = "\n".join(inner)

    return response_text
