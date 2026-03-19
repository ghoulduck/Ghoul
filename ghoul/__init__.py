"""
Ghoul — a self-improving AI agent powered by Anthropic Claude.
"""

__version__ = "0.1.0"
__author__ = "Ghoul"
__description__ = "A self-improving AI agent powered by Anthropic Claude"


def strip_markdown_fences(text: str) -> str:
    """Strip optional markdown code fences from an LLM response."""
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        text = "\n".join(inner)
    return text
