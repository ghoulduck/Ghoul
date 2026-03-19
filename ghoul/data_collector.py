"""
ghoul/data_collector.py — Autonomous Data Collector.

Collects training data from multiple sources:
  - Web scraping (requests + BeautifulSoup)
  - GitHub API (searches for relevant repos and files)
  - Synthetic generation (Claude produces prompt/completion pairs)

Stores collected data in JSONL format under the configured data/ directory.
No rate limiting, no filtering — collects aggressively.
"""

import json
import time
from pathlib import Path

import anthropic
import requests
from bs4 import BeautifulSoup

from ghoul.config import CFG
from ghoul.memory import Memory


# ---------------------------------------------------------------------------
# Web Scraping
# ---------------------------------------------------------------------------

def scrape_url(url: str) -> list[dict]:
    """
    Scrape code examples and text from *url*.

    Returns a list of dicts with keys: source, content, url, scraped_at.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; GhoulBot/1.0)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    samples = []

    # Grab all <code> and <pre> blocks
    for tag in soup.find_all(["code", "pre"]):
        text = tag.get_text(strip=True)
        if len(text) > 30:
            samples.append(
                {
                    "source": "web_scrape",
                    "url": url,
                    "content": text,
                    "scraped_at": time.time(),
                }
            )

    # Also grab paragraph text as documentation snippets
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) > 100:
            samples.append(
                {
                    "source": "web_scrape_text",
                    "url": url,
                    "content": text,
                    "scraped_at": time.time(),
                }
            )

    return samples


def scrape_urls(urls: list[str]) -> list[dict]:
    """Scrape multiple URLs and aggregate results."""
    all_samples: list[dict] = []
    for url in urls:
        try:
            samples = scrape_url(url)
            all_samples.extend(samples)
        except Exception as exc:
            print(f"[DataCollector] Failed to scrape {url}: {exc}")
    return all_samples


# ---------------------------------------------------------------------------
# GitHub API
# ---------------------------------------------------------------------------

def search_github(query: str, max_repos: int = 10) -> list[dict]:
    """
    Search GitHub for repositories matching *query* and fetch Python files.

    Returns a list of dicts: source, repo, path, content, fetched_at.
    """
    token = CFG.get("github_token", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Search repos
    search_url = "https://api.github.com/search/repositories"
    params = {"q": query, "sort": "stars", "per_page": max_repos}
    resp = requests.get(search_url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    repos = resp.json().get("items", [])

    samples: list[dict] = []
    for repo in repos:
        full_name = repo["full_name"]
        # Fetch the file tree (top level only)
        tree_url = f"https://api.github.com/repos/{full_name}/git/trees/HEAD"
        try:
            tree_resp = requests.get(tree_url, headers=headers, timeout=30)
            tree_resp.raise_for_status()
            tree = tree_resp.json().get("tree", [])
        except Exception:
            continue

        for item in tree:
            if item.get("type") == "blob" and item.get("path", "").endswith(".py"):
                raw_url = (
                    f"https://raw.githubusercontent.com/{full_name}/HEAD/{item['path']}"
                )
                try:
                    file_resp = requests.get(raw_url, timeout=30)
                    file_resp.raise_for_status()
                    samples.append(
                        {
                            "source": "github",
                            "repo": full_name,
                            "path": item["path"],
                            "content": file_resp.text,
                            "fetched_at": time.time(),
                        }
                    )
                except Exception:
                    continue

    return samples


# ---------------------------------------------------------------------------
# Synthetic Data Generation
# ---------------------------------------------------------------------------

_SYNTH_SYSTEM = """\
You are a training data generator for a Python coding AI.
Given a topic, generate 5 distinct prompt/completion pairs as a JSON array:
[
  {"prompt": "...", "completion": "..."},
  ...
]
Each "prompt" is a coding task and "completion" is the full Python solution.
Return ONLY valid JSON — no markdown fences, no extra text.
"""


def generate_synthetic(topic: str, count: int = 5) -> list[dict]:
    """
    Use Claude to generate *count* synthetic prompt/completion pairs on *topic*.
    """
    client = anthropic.Anthropic(api_key=CFG["anthropic_api_key"])

    message = client.messages.create(
        model=CFG["model"],
        max_tokens=4096,
        system=_SYNTH_SYSTEM,
        messages=[
            {
                "role": "user",
                "content": (
                    f"Generate {count} Python coding prompt/completion pairs "
                    f"on the topic: {topic}"
                ),
            }
        ],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    try:
        pairs = json.loads(raw)
    except json.JSONDecodeError:
        pairs = []

    timestamp = time.time()
    return [
        {
            "source": "synthetic",
            "topic": topic,
            "prompt": p.get("prompt", ""),
            "completion": p.get("completion", ""),
            "generated_at": timestamp,
        }
        for p in pairs
        if isinstance(p, dict)
    ]


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def save_jsonl(samples: list[dict], path: Path) -> None:
    """Append *samples* to a JSONL file at *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        for sample in samples:
            f.write(json.dumps(sample) + "\n")


# ---------------------------------------------------------------------------
# High-level collect function
# ---------------------------------------------------------------------------

def collect(
    topic: str,
    urls: list[str] | None = None,
    github_query: str | None = None,
    synthetic_count: int = 10,
    memory: Memory | None = None,
) -> Path:
    """
    Collect training data on *topic* from all sources and save to JSONL.

    Parameters
    ----------
    topic:           Topic label used to name the output file.
    urls:            Optional list of URLs to scrape.
    github_query:    Optional GitHub search query (defaults to topic).
    synthetic_count: Number of synthetic examples to generate.
    memory:          Optional Memory instance to record the collection event.

    Returns
    -------
    Path to the JSONL file.
    """
    data_dir: Path = CFG["data_dir"]
    safe_topic = topic.replace(" ", "_").replace("/", "_")[:64]
    out_path = data_dir / f"training_{safe_topic}_{int(time.time())}.jsonl"

    all_samples: list[dict] = []

    # 1. Web scraping
    if urls:
        print(f"[DataCollector] Scraping {len(urls)} URL(s)…")
        scraped = scrape_urls(urls)
        all_samples.extend(scraped)
        print(f"[DataCollector] Scraped {len(scraped)} samples.")

    # 2. GitHub
    gq = github_query or topic
    print(f"[DataCollector] Searching GitHub for '{gq}'…")
    try:
        github_samples = search_github(gq)
        all_samples.extend(github_samples)
        print(f"[DataCollector] Fetched {len(github_samples)} GitHub samples.")
    except Exception as exc:
        print(f"[DataCollector] GitHub search failed: {exc}")

    # 3. Synthetic
    print(f"[DataCollector] Generating {synthetic_count} synthetic examples…")
    synth = generate_synthetic(topic, count=synthetic_count)
    all_samples.extend(synth)
    print(f"[DataCollector] Generated {len(synth)} synthetic samples.")

    # Save
    save_jsonl(all_samples, out_path)
    print(f"[DataCollector] Saved {len(all_samples)} total samples → {out_path}")

    if memory:
        memory.record_data_collection(
            source=f"web+github+synthetic",
            count=len(all_samples),
            path=str(out_path),
        )

    return out_path
