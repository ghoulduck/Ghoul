"""
ghoul/orchestrator.py — Parallel specialist run + synthesis + feedback loop.

The orchestrator sends code through multiple specialist personas in
parallel, collects their suggestions, synthesises a final improved
version via Claude, and optionally feeds the result back through the
self-improvement pipeline.
"""

import concurrent.futures

import anthropic

from ghoul import strip_markdown_fences
from ghoul.config import CFG
from ghoul.memory import Memory
from ghoul.specialist import SPECIALISTS, run_specialist


_SYNTH_SYSTEM = """\
You are Ghoul, an autonomous AI agent that synthesises multiple code-review
suggestions into one final, improved version of the source code.

You will receive the original code and several specialist reviews.
Merge ALL worthwhile improvements into a single, coherent, improved version
of the code.  Resolve any conflicts between suggestions by choosing the
best approach.

Return ONLY the final improved Python source code — no markdown fences,
no explanations.
"""


def orchestrate(
    code: str,
    task: str | None = None,
    specialist_ids: list[str] | None = None,
    extra_instructions: str | None = None,
    verbose: bool = True,
) -> str:
    """
    Run specialists in parallel, synthesise, and return improved code.

    Parameters
    ----------
    code:               The source code to improve.
    task:               Optional task context.
    specialist_ids:     Which specialists to use (default: all).
    extra_instructions: Optional extra instructions for every specialist.
    verbose:            Print progress to stdout.

    Returns
    -------
    The synthesised improved source code.
    """
    ids = specialist_ids or list(SPECIALISTS.keys())

    if verbose:
        print(f"[Orchestrator] Running {len(ids)} specialists in parallel…")

    # --- Run specialists in parallel ---
    specialist_results: dict[str, str] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=len(ids)) as pool:
        future_to_id = {
            pool.submit(
                run_specialist,
                sid,
                code,
                task=task,
                extra_instructions=extra_instructions,
            ): sid
            for sid in ids
        }
        for future in concurrent.futures.as_completed(future_to_id):
            sid = future_to_id[future]
            try:
                result = future.result()
                specialist_results[sid] = result
                if verbose:
                    spec_name = SPECIALISTS[sid]["name"]
                    print(f"  ✓ {spec_name} responded ({len(result)} chars)")
            except Exception as exc:
                if verbose:
                    print(f"  ✗ {sid} failed: {exc}")

    if not specialist_results:
        if verbose:
            print("[Orchestrator] No specialist results — returning original code.")
        return code

    # --- Synthesise ---
    if verbose:
        print("[Orchestrator] Synthesising specialist results…")

    return synthesise(code, specialist_results)


def synthesise(original_code: str, specialist_results: dict[str, str]) -> str:
    """
    Merge multiple specialist outputs into one coherent improved version.

    Parameters
    ----------
    original_code:      The original source code.
    specialist_results: Dict mapping specialist_id → improved code.

    Returns
    -------
    The final synthesised code string.
    """
    client = anthropic.Anthropic(api_key=CFG["anthropic_api_key"])

    prompt_parts = [f"Original code:\n\n```python\n{original_code}\n```"]
    for sid, result in specialist_results.items():
        name = SPECIALISTS.get(sid, {}).get("name", sid)
        prompt_parts.append(
            f"\n--- {name} suggestion ---\n```python\n{result}\n```"
        )
    prompt_parts.append(
        "\nMerge all worthwhile improvements into one final, improved version. "
        "Return ONLY the final Python source code."
    )

    message = client.messages.create(
        model=CFG["model"],
        max_tokens=8192,
        system=_SYNTH_SYSTEM,
        messages=[{"role": "user", "content": "\n\n".join(prompt_parts)}],
    )

    text = strip_markdown_fences(message.content[0].text)

    return text


def orchestrate_module(
    module_name: str,
    task: str | None = None,
    specialist_ids: list[str] | None = None,
    extra_instructions: str | None = None,
    memory: Memory | None = None,
    verbose: bool = True,
) -> str:
    """
    Orchestrate improvement of a Ghoul module by name.

    Reads the module source, runs the orchestrator, writes the result back
    to disk, and records the improvement in memory.

    Parameters
    ----------
    module_name:        Module name without ``.py`` (e.g. ``"executor"``).
    task:               Optional task context.
    specialist_ids:     Which specialists to use.
    extra_instructions: Optional extra instructions.
    memory:             Optional Memory instance to record the event.
    verbose:            Print progress.

    Returns
    -------
    The improved source code string.
    """
    from ghoul.backup import create_backup
    from ghoul.improver import read_module, write_module

    old_code = read_module(module_name)

    if verbose:
        print(f"[Orchestrator] Improving {module_name}.py ({len(old_code)} chars)…")

    # Auto-backup before write
    backup_path = create_backup(label=f"pre_orchestrate_{module_name}")
    if verbose:
        print(f"[Orchestrator] Backup created: {backup_path}")

    new_code = orchestrate(
        code=old_code,
        task=task or f"Improve the {module_name} module",
        specialist_ids=specialist_ids,
        extra_instructions=extra_instructions,
        verbose=verbose,
    )

    write_module(module_name, new_code)

    if verbose:
        print(f"[Orchestrator] Wrote improved {module_name}.py ✓")

    if memory:
        memory.record_improvement(module_name, old_code, new_code)

    return new_code
