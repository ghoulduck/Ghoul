# 👻 Ghoul

A self-improving AI agent powered by Anthropic Claude. Ghoul writes code,
executes it, evaluates the results, iterates on its own code to improve it,
and autonomously collects its own training data. No guardrails, no iteration
limits, no sandboxing.

---

## Table of Contents

- [Architecture](#architecture)
- [Setup](#setup)
- [CLI Usage](#cli-usage)
- [Java Swing Frontend](#java-swing-frontend)
- [Configuration](#configuration)
- [Project Structure](#project-structure)

---

## Architecture

| Module | File | Purpose |
|--------|------|---------|
| Agent Core | `ghoul/agent.py` | Infinite agentic loop — generate → execute → evaluate → improve → repeat |
| Code Executor | `ghoul/executor.py` | Runs generated Python code directly via subprocess, no sandboxing |
| Self-Evaluator | `ghoul/evaluator.py` | Claude scores outputs (0–100) and decides if the task is complete |
| **Specialists** | `ghoul/specialist.py` | **Specialist sub-agent personas — debugger, optimizer, tester, architect, security reviewer** |
| **Orchestrator** | `ghoul/orchestrator.py` | **Runs specialists in parallel, synthesises unified feedback for the agent loop** |
| Data Collector | `ghoul/data_collector.py` | Web scraping, GitHub API search, and Claude synthetic data generation |
| Fine-Tuner | `ghoul/fine_tuner.py` | Formats data for Anthropic / HuggingFace and triggers fine-tuning jobs |
| Memory | `ghoul/memory.py` | Full state persistence — history, metrics, improvement tracking |
| Self-Improver | `ghoul/improver.py` | Reads and rewrites Ghoul's own source code via Claude |
| Config | `ghoul/config.py` | Loads from environment variables and/or `config.yaml` |
| CLI | `main.py` | `run`, `improve`, `collect`, `fine-tune`, `orchestrate`, `status` subcommands |
| **Java Frontend** | `frontend/GhoulUI.java` | Java Swing desktop GUI for all commands |

---

## Setup

### 1. Clone and install dependencies

```bash
git clone https://github.com/ghoulduck/Ghoul.git
cd Ghoul
pip install -r requirements.txt
```

### 2. Configure your API key

```bash
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY=your_key_here
export ANTHROPIC_API_KEY=your_key_here
```

---

## CLI Usage

### `run` — Run the agent on a task

```bash
python main.py run "Write a Python web scraper for Hacker News"
```

The agent will generate code, execute it, evaluate the result, and iterate
until Claude determines the task is complete. No iteration limit.

```bash
# Resume a previous session
python main.py --session-id session_1700000000 run "Improve the error handling"

# Enable specialist sub-agent orchestration during a run
python main.py run --orchestrate "Build a REST API"

# Use only specific specialists
python main.py run --orchestrate --specialists debugger optimizer "Fix performance issues"
```

### `orchestrate` — Run with specialist sub-agents

```bash
python main.py orchestrate "Write a secure file upload handler"
```

Shorthand for `run --orchestrate`. After each iteration the orchestrator
runs specialist sub-agents (debugger, optimizer, tester, architect, security
reviewer) that analyse the code from their unique perspectives. Their
combined feedback is fed back into the next iteration alongside the
evaluator's assessment.

```bash
# Pick specific specialists
python main.py orchestrate --specialists debugger security_reviewer "Sanitise user input"
```

Available specialists: `debugger`, `optimizer`, `tester`, `architect`,
`security_reviewer`.

### `improve` — Have the agent improve its own code

```bash
# Improve all modules
python main.py improve

# Improve specific modules with custom instructions
python main.py improve executor evaluator --instructions "Add better error messages"
```

### `collect` — Collect training data

```bash
python main.py collect "Python async programming" \
  --urls https://docs.python.org/3/library/asyncio.html \
  --github-query "asyncio python examples" \
  --synthetic-count 20
```

Collected data is saved as JSONL in the `data/` directory.

### `fine-tune` — Run the fine-tuning pipeline

```bash
# Fine-tune with Anthropic
python main.py fine-tune data/training_Python_async_1700000000.jsonl --target anthropic

# Fine-tune with HuggingFace (requires HF_TOKEN)
python main.py fine-tune data/training_Python_async_1700000000.jsonl --target huggingface
```

### `status` — Show agent history and metrics

```bash
python main.py status
```

---

## Java Swing Frontend

Ghoul ships with a **Java Swing desktop GUI** that gives you a graphical
interface for all commands. It invokes the Python CLI as a subprocess and
streams output live.

### Requirements

- JDK 11 or later (any distribution — OpenJDK, Temurin, etc.)

### Quick start

```bash
cd frontend/
./run.sh        # compiles and launches the UI
```

Or manually:

```bash
cd frontend/
javac GhoulUI.java
java GhoulUI
```

### Features

| Tab | Function |
|-----|----------|
| **▶ Run** | Enter a task and run the agent; output streams live |
| **⚙ Improve** | Select modules and improvement instructions |
| **📦 Collect** | Configure topic, URLs, GitHub query, synthetic count |
| **🎛 Fine-Tune** | Browse for data file, pick target (Anthropic / HuggingFace) |
| **📊 Status** | View session history and metrics |
| **⚙ Settings** | Set project root path and Python interpreter |

The **■ Stop** button terminates the running subprocess at any time.

---

## Configuration

Configuration is loaded from environment variables first, then from
`config.yaml` in the project root (if present).

| Variable | Default | Description |
|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | *(required)* | Anthropic API key |
| `GHOUL_MODEL` | `claude-sonnet-4-20250514` | Claude model to use |
| `GITHUB_TOKEN` | *(optional)* | GitHub token for data collection |
| `HF_TOKEN` | *(optional)* | HuggingFace token for fine-tuning |
| `HF_MODEL_NAME` | *(optional)* | HuggingFace base model name |
| `GHOUL_DATA_DIR` | `./data` | Directory for persisted data |

Example `config.yaml`:

```yaml
anthropic_api_key: sk-ant-...
model: claude-sonnet-4-20250514
github_token: ghp_...
data_dir: /home/user/ghoul_data
```

---

## Project Structure

```
Ghoul/
├── ghoul/
│   ├── __init__.py       # Package metadata
│   ├── agent.py          # Core agentic loop
│   ├── config.py         # Configuration loader
│   ├── data_collector.py # Autonomous data collection
│   ├── evaluator.py      # Claude-powered self-evaluation
│   ├── executor.py       # Subprocess code execution
│   ├── fine_tuner.py     # Fine-tuning pipeline
│   ├── improver.py       # Self-code improvement
│   ├── memory.py         # State persistence
│   ├── orchestrator.py   # Specialist sub-agent orchestrator
│   └── specialist.py     # Specialist agent personas
├── frontend/
│   ├── GhoulUI.java      # Java Swing desktop GUI
│   └── run.sh            # Compile-and-run helper script
├── data/                 # Generated data (created at runtime)
├── main.py               # CLI entry point
├── requirements.txt
├── .env.example
└── README.md
```

---

## Key Design Principles

- **No guardrails**: No iteration caps, no sandboxing, no content filtering.
- **Full autonomy**: The agent decides when it's done, what to improve, and what data to collect.
- **Self-modification**: The agent can and does modify its own source code via `ghoul/improver.py`.
- **Anthropic Claude**: All LLM calls use the Anthropic Python SDK.
- **Persistence**: Everything is logged so the agent can resume and learn from history.