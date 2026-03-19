"""
ghoul/specialist.py — Specialist Coding-Agent Personas.

Defines specialized sub-agents, each with a unique persona and system prompt
that gives them a focused expertise (debugging, optimization, testing,
architecture, security review).

Each specialist can analyze a task + code + execution result from its own
perspective and return structured feedback.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import anthropic

from ghoul.config import CFG


# ---------------------------------------------------------------------------
# Specialist definition
# ---------------------------------------------------------------------------

@dataclass
class Specialist:
    """A sub-agent with a specific coding expertise."""

    name: str
    description: str
    system_prompt: str
    # Optional list of focus keywords — informational only
    focus_areas: list[str] = field(default_factory=list)

    def analyze(
        self,
        task: str,
        code: str,
        execution_result: dict,
    ) -> dict:
        """
        Ask this specialist to analyze *code* in the context of *task*.

        Parameters
        ----------
        task:             The original task description.
        code:             The Python code under review.
        execution_result: Dict with stdout, stderr, returncode, duration.

        Returns
        -------
        dict with keys:
            specialist  — name of this specialist
            findings    — list[str] of observations / suggestions
            score       — int 0-100 from this specialist's perspective
            summary     — one-sentence overall assessment
        """
        client = anthropic.Anthropic(api_key=CFG["anthropic_api_key"])

        user_msg = (
            f"Task:\n{task}\n\n"
            f"Code:\n```python\n{code}\n```\n\n"
            f"Execution result:\n"
            f"- Return code: {execution_result.get('returncode')}\n"
            f"- Duration: {execution_result.get('duration')}s\n"
            f"- stdout:\n{execution_result.get('stdout', '(empty)')}\n"
            f"- stderr:\n{execution_result.get('stderr', '(empty)')}\n\n"
            "Analyze the code from your specialist perspective and return a "
            "JSON object with EXACTLY these fields:\n"
            '{\n'
            '  "findings": ["<finding 1>", "<finding 2>", ...],\n'
            '  "score": <integer 0-100>,\n'
            '  "summary": "<one-sentence assessment>"\n'
            '}\n'
            "Return ONLY valid JSON — no markdown fences, no extra text."
        )

        message = client.messages.create(
            model=CFG["model"],
            max_tokens=2048,
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )

        raw = message.content[0].text.strip()

        # Strip accidental markdown fences
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            result = {
                "findings": [raw],
                "score": 0,
                "summary": "Specialist could not parse response.",
            }

        result["specialist"] = self.name
        return result


# ---------------------------------------------------------------------------
# Pre-defined specialist personas
# ---------------------------------------------------------------------------

DEBUGGER = Specialist(
    name="debugger",
    description="Finds bugs, logic errors, and runtime failures.",
    system_prompt=(
        "You are a specialist debugging agent. Your sole focus is finding bugs, "
        "logic errors, off-by-one mistakes, unhandled exceptions, type errors, "
        "and runtime failures in Python code. Be thorough and precise."
    ),
    focus_areas=["bugs", "exceptions", "logic errors", "runtime failures"],
)

OPTIMIZER = Specialist(
    name="optimizer",
    description="Improves performance, memory usage, and algorithmic efficiency.",
    system_prompt=(
        "You are a specialist performance-optimisation agent. Your sole focus is "
        "improving execution speed, reducing memory usage, choosing better data "
        "structures and algorithms, and eliminating unnecessary work. "
        "Be specific about what to change and why."
    ),
    focus_areas=["performance", "memory", "algorithms", "complexity"],
)

TESTER = Specialist(
    name="tester",
    description="Identifies missing test coverage and edge cases.",
    system_prompt=(
        "You are a specialist testing and quality-assurance agent. Your sole "
        "focus is identifying missing test cases, untested edge cases, boundary "
        "conditions, and suggesting concrete test code. "
        "Be specific about what scenarios are untested."
    ),
    focus_areas=["testing", "edge cases", "coverage", "assertions"],
)

ARCHITECT = Specialist(
    name="architect",
    description="Reviews code structure, modularity, and design patterns.",
    system_prompt=(
        "You are a specialist software architecture agent. Your sole focus is "
        "evaluating code structure, separation of concerns, modularity, "
        "appropriate use of design patterns, and maintainability. "
        "Suggest concrete structural improvements."
    ),
    focus_areas=["structure", "modularity", "design patterns", "maintainability"],
)

SECURITY_REVIEWER = Specialist(
    name="security_reviewer",
    description="Identifies security vulnerabilities and unsafe practices.",
    system_prompt=(
        "You are a specialist security review agent. Your sole focus is finding "
        "security vulnerabilities: injection attacks, unsafe input handling, "
        "hardcoded secrets, insecure subprocess usage, path traversal, and "
        "other OWASP-style issues. Be specific about the risk and remediation."
    ),
    focus_areas=["security", "vulnerabilities", "injection", "input validation"],
)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SPECIALISTS: dict[str, Specialist] = {
    "debugger": DEBUGGER,
    "optimizer": OPTIMIZER,
    "tester": TESTER,
    "architect": ARCHITECT,
    "security_reviewer": SECURITY_REVIEWER,
}


def get_specialist(name: str) -> Specialist:
    """Return a specialist by *name*, or raise ``KeyError``."""
    if name not in SPECIALISTS:
        available = ", ".join(sorted(SPECIALISTS))
        raise KeyError(
            f"Unknown specialist '{name}'. Available: {available}"
        )
    return SPECIALISTS[name]


def list_specialists() -> list[str]:
    """Return the names of all registered specialists."""
    return sorted(SPECIALISTS)
