"""
ghoul/improver.py — Self-Code Improvement.

The agent reads its own source code, sends it to Claude, receives an
improved version, and writes it back to disk — replacing its own files.

No restrictions on what it can modify.
"""

from pathlib import Path

import anthropic

from ghoul.config import CFG
from ghoul.memory import Memory


_ROOT = Path(__file__).parent  # ghoul/ package directory


_IMPROVE_SYSTEM = """\
You are an expert Python engineer performing a targeted code improvement.
You will be given the source code of a module and asked to improve it.

Your improvements should:
- Fix any bugs or logic errors.
- Improve code quality, readability, and robustness.
- Enhance performance where possible.
- Add missing error handling.
- Keep all existing functionality intact.

Return ONLY the improved Python source code — no markdown fences,
no explanations, no extra text.
"""


def read_module(module_name: str) -> str:
    """
    Read the source of a Ghoul module by name.

    Parameters
    ----------
    module_name: e.g. 'executor', 'evaluator', 'agent', 'improver'.

    Returns the source code as a string.
    """
    path = _ROOT / f"{module_name}.py"
    if not path.exists():
        raise FileNotFoundError(f"Module '{module_name}' not found at {path}")
    return path.read_text()


def write_module(module_name: str, code: str) -> None:
    """Write improved *code* back to the module file, replacing it."""
    path = _ROOT / f"{module_name}.py"
    path.write_text(code)


def improve_module(
    module_name: str,
    instructions: str | None = None,
    specialist_insights: list[str] | None = None,
    memory: Memory | None = None,
    verbose: bool = True,
) -> str:
    """
    Ask Claude to improve a Ghoul module and write the result back to disk.

    Parameters
    ----------
    module_name:          Name of the module to improve (without .py).
    instructions:         Optional specific improvement instructions.
    specialist_insights:  Optional list of findings from specialist sub-agents.
    memory:               Optional Memory instance to record the improvement.
    verbose:              Print progress to stdout.

    Returns
    -------
    The improved source code string.
    """
    client = anthropic.Anthropic(api_key=CFG["anthropic_api_key"])

    old_code = read_module(module_name)

    if verbose:
        print(f"[Improver] Reading {module_name}.py ({len(old_code)} chars)…")

    prompt_parts = [
        f"Here is the source code of the `{module_name}` module:\n\n```python\n{old_code}\n```",
    ]
    if instructions:
        prompt_parts.append(f"\nSpecific improvement instructions:\n{instructions}")
    if specialist_insights:
        prompt_parts.append("\nFindings from specialist sub-agents:")
        for insight in specialist_insights:
            prompt_parts.append(f"  • {insight}")
    prompt_parts.append(
        "\nPlease improve this code. Return ONLY the improved Python source code."
    )

    message = client.messages.create(
        model=CFG["model"],
        max_tokens=8192,
        system=_IMPROVE_SYSTEM,
        messages=[{"role": "user", "content": "\n".join(prompt_parts)}],
    )

    new_code = message.content[0].text.strip()

    # Strip accidental markdown fences
    if new_code.startswith("```"):
        lines = new_code.splitlines()
        inner = lines[1:-1] if lines[-1].strip() == "```" else lines[1:]
        new_code = "\n".join(inner)

    if verbose:
        print(f"[Improver] Received improved code ({len(new_code)} chars).")

    write_module(module_name, new_code)

    if verbose:
        print(f"[Improver] Wrote improved {module_name}.py to disk ✓")

    if memory:
        memory.record_improvement(module_name, old_code, new_code)

    return new_code


def improve_all(
    modules: list[str] | None = None,
    instructions: str | None = None,
    specialist_insights: list[str] | None = None,
    memory: Memory | None = None,
    verbose: bool = True,
) -> dict[str, str]:
    """
    Improve multiple Ghoul modules.

    Parameters
    ----------
    modules:              List of module names to improve. Defaults to all
                          core modules.
    instructions:         Optional improvement instructions applied to each
                          module.
    specialist_insights:  Optional list of specialist findings applied to each
                          module.
    memory:               Optional Memory instance.
    verbose:              Print progress.

    Returns
    -------
    Dict of {module_name: improved_code}.
    """
    if modules is None:
        modules = [
            "agent",
            "executor",
            "evaluator",
            "data_collector",
            "fine_tuner",
            "memory",
            "improver",
            "config",
            "specialist",
            "orchestrator",
        ]

    results: dict[str, str] = {}
    for module in modules:
        try:
            results[module] = improve_module(
                module,
                instructions=instructions,
                specialist_insights=specialist_insights,
                memory=memory,
                verbose=verbose,
            )
        except Exception as exc:
            print(f"[Improver] Failed to improve {module}: {exc}")

    return results
