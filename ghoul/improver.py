"""
ghoul/improver.py — Self-Code Improvement.

The agent reads its own source code, sends it to Claude, receives an
improved version, and writes it back to disk — replacing its own files.

No restrictions on what it can modify.

Supports auto-backup before writes and optional specialist insights via
the orchestrator.
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
    memory: Memory | None = None,
    verbose: bool = True,
    use_specialists: bool = False,
    auto_backup: bool = True,
) -> str:
    """
    Ask Claude to improve a Ghoul module and write the result back to disk.

    Parameters
    ----------
    module_name:     Name of the module to improve (without .py).
    instructions:    Optional specific improvement instructions.
    memory:          Optional Memory instance to record the improvement.
    verbose:         Print progress to stdout.
    use_specialists: If True, also run specialist personas via the
                     orchestrator and merge insights.
    auto_backup:     If True, create a backup before writing changes.

    Returns
    -------
    The improved source code string.
    """
    client = anthropic.Anthropic(api_key=CFG["anthropic_api_key"])

    old_code = read_module(module_name)

    if verbose:
        print(f"[Improver] Reading {module_name}.py ({len(old_code)} chars)…")

    # Auto-backup before modification
    if auto_backup:
        try:
            from ghoul.backup import create_backup

            backup_path = create_backup(label=f"pre_improve_{module_name}")
            if verbose:
                print(f"[Improver] Backup created: {backup_path}")
        except Exception as exc:
            if verbose:
                print(f"[Improver] Backup failed (continuing): {exc}")

    if verbose:
        print(f"[Improver] Reading {module_name}.py ({len(old_code)} chars)…")

    prompt_parts = [
        f"Here is the source code of the `{module_name}` module:\n\n```python\n{old_code}\n```",
    ]
    if instructions:
        prompt_parts.append(f"\nSpecific improvement instructions:\n{instructions}")
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

    # Optional: run specialist insights and merge
    if use_specialists:
        try:
            from ghoul.orchestrator import orchestrate

            if verbose:
                print(f"[Improver] Running specialist personas for additional insights…")
            specialist_code = orchestrate(
                code=new_code,
                task=f"Further improve the {module_name} module",
                verbose=verbose,
            )
            write_module(module_name, specialist_code)
            new_code = specialist_code
            if verbose:
                print(f"[Improver] Specialist insights applied to {module_name}.py ✓")
        except Exception as exc:
            if verbose:
                print(f"[Improver] Specialist pass failed (keeping base improvement): {exc}")

    if memory:
        memory.record_improvement(module_name, old_code, new_code)

    return new_code


def improve_all(
    modules: list[str] | None = None,
    instructions: str | None = None,
    memory: Memory | None = None,
    verbose: bool = True,
    use_specialists: bool = False,
) -> dict[str, str]:
    """
    Improve multiple Ghoul modules.

    Parameters
    ----------
    modules:         List of module names to improve. Defaults to all core modules.
    instructions:    Optional improvement instructions applied to each module.
    memory:          Optional Memory instance.
    verbose:         Print progress.
    use_specialists: Also run specialist personas for additional insights.

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
        ]

    results: dict[str, str] = {}
    for module in modules:
        try:
            results[module] = improve_module(
                module,
                instructions=instructions,
                memory=memory,
                verbose=verbose,
                use_specialists=use_specialists,
            )
        except Exception as exc:
            print(f"[Improver] Failed to improve {module}: {exc}")

    return results
