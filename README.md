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
- [Building & Packaging](#building--packaging)
- [Configuration](#configuration)
- [Project Structure](#project-structure)

---

## Architecture

| Module | File | Purpose |
|--------|------|---------|
| Agent Core | `ghoul/agent.py` | Infinite agentic loop — generate → execute → evaluate → improve → repeat |
| Code Executor | `ghoul/executor.py` | Runs generated Python code directly via subprocess, no sandboxing |
| Self-Evaluator | `ghoul/evaluator.py` | Claude scores outputs (0–100) and decides if the task is complete |
| Data Collector | `ghoul/data_collector.py` | Exhaustive web crawling, full GitHub repo scraping, code search, and Claude synthetic data generation |
| Fine-Tuner | `ghoul/fine_tuner.py` | Formats data for Anthropic / HuggingFace and triggers fine-tuning jobs |
| Memory | `ghoul/memory.py` | Full state persistence — history, metrics, improvement tracking |
| Self-Improver | `ghoul/improver.py` | Reads and rewrites Ghoul's own source code via Claude, with auto-backup |
| Specialist | `ghoul/specialist.py` | Specialist coding-agent personas (architect, security, performance, etc.) |
| Orchestrator | `ghoul/orchestrator.py` | Parallel specialist run + synthesis + self-improvement feedback loop |
| Backup | `ghoul/backup.py` | Timestamped ZIP snapshots of source code and session data |
| Config | `ghoul/config.py` | Loads from environment variables and/or `config.yaml` |
| CLI | `main.py` | `run`, `improve`, `orchestrate`, `collect`, `fine-tune`, `status` subcommands |
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
```

### `improve` — Have the agent improve its own code

```bash
# Improve all modules (with auto-backup)
python main.py improve

# Improve specific modules with custom instructions
python main.py improve executor evaluator --instructions "Add better error messages"

# Also run specialist personas for additional insights
python main.py improve --specialists
```

### `orchestrate` — Run specialist personas to improve code

```bash
# Orchestrate all modules through all specialist personas
python main.py orchestrate

# Orchestrate specific modules with specific specialists
python main.py orchestrate executor evaluator \
  --specialists architect,security,performance \
  --instructions "Focus on robustness"
```

Available specialists: `architect`, `algorithms`, `security`, `testing`,
`performance`, `readability`.

### `collect` — Collect training data

```bash
python main.py collect "Python async programming" \
  --urls https://docs.python.org/3/library/asyncio.html \
  --github-query "asyncio python examples" \
  --synthetic-count 50 \
  --max-repos 100 \
  --max-files-per-repo 200 \
  --crawl-depth 3 \
  --crawl-max-pages 200
```

The data collector works exhaustively:
- **Web scraping**: Deep-crawls seed URLs, follows links up to the
  configured depth, extracts code blocks, documentation text, headings,
  lists, tables, and full-page content from every page visited.
- **GitHub scraping**: Searches for up to 100 repos (paginated), fetches
  the full recursive file tree of each repo, downloads every code and
  documentation file (`.py`, `.js`, `.ts`, `.go`, `.rs`, `.md`, `.rst`,
  `.yaml`, and dozens more extensions). Also runs a GitHub code search to
  find additional relevant files across all of GitHub.
- **Synthetic generation**: Uses Claude to generate diverse
  prompt/completion pairs in batches, covering beginner to advanced
  difficulty levels.

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
| **🔀 Orchestrate** | Run specialist personas to improve modules |
| **📦 Collect** | Configure topic, URLs, GitHub query, synthetic count |
| **🎛 Fine-Tune** | Browse for data file, pick target (Anthropic / HuggingFace) |
| **📊 Status** | View session history and metrics |
| **📜 History** | Detailed session history viewer with refresh |
| **⚙ Settings** | Set project root path and Python interpreter |

The **■ Stop** button terminates the running subprocess at any time.

The frontend automatically detects bundled executables (`ghoul` / `ghoul.exe`)
next to the class file and will use those instead of `python main.py` when
available.

---

## Building & Packaging

Ghoul includes tooling to build standalone executables and installers.

### Python standalone EXE (PyInstaller)

```bash
pip install pyinstaller
pyinstaller ghoul.spec --noconfirm
# Output: dist/ghoul/
```

### Java fat JAR (Gradle Shadow)

```bash
gradle shadowJar
java -jar build/libs/ghoul-ui-all.jar
```

### Native installer (jpackage, requires JDK 14+)

```bash
gradle jpackageImage
# Output: build/jpackage/
```

### Master build script

```bash
# Build everything
python build.py

# Python only
python build.py --python-only

# Java only
python build.py --java-only

# Include native installer
python build.py --installer

# Compile Java directly (no Gradle needed)
python build.py --java-only --no-gradle
```

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
│   ├── __init__.py        # Package metadata
│   ├── agent.py           # Core agentic loop (with orchestrator integration)
│   ├── backup.py          # Timestamped ZIP backup snapshots
│   ├── config.py          # Configuration loader
│   ├── data_collector.py  # Exhaustive data collection (web + GitHub + synthetic)
│   ├── evaluator.py       # Claude-powered self-evaluation
│   ├── executor.py        # Subprocess code execution
│   ├── fine_tuner.py      # Fine-tuning pipeline
│   ├── improver.py        # Self-code improvement (with auto-backup + specialists)
│   ├── memory.py          # State persistence
│   ├── orchestrator.py    # Parallel specialist orchestration + synthesis
│   └── specialist.py      # Specialist coding-agent personas
├── frontend/
│   ├── GhoulUI.java       # Java Swing desktop GUI
│   └── run.sh             # Compile-and-run helper script
├── data/                  # Generated data (created at runtime)
├── backups/               # Backup snapshots (created at runtime)
├── main.py                # CLI entry point
├── build.py               # Master build orchestration script
├── build.gradle           # Gradle Shadow JAR + jpackage config
├── ghoul.spec             # PyInstaller spec for standalone EXE
├── requirements.txt
├── .env.example
└── README.md
```

---

## Key Design Principles

- **No guardrails**: No iteration caps, no sandboxing, no content filtering.
- **Full autonomy**: The agent decides when it's done, what to improve, and what data to collect.
- **Self-modification**: The agent can and does modify its own source code via `ghoul/improver.py`.
- **Exhaustive data collection**: Scrapes every reachable GitHub repository and documentation page for maximum proficiency.
- **Specialist orchestration**: Multiple AI personas review code in parallel and their insights are synthesised.
- **Anthropic Claude**: All LLM calls use the Anthropic Python SDK.
- **Persistence**: Everything is logged so the agent can resume and learn from history.
- **Auto-backup**: Source code is backed up before any self-modification.