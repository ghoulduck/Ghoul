"""
ghoul/data_collector.py — Autonomous Data Collector.

Collects training data from multiple sources:
  - Web scraping (requests + BeautifulSoup) — deep crawl with link following
  - GitHub API — full recursive tree traversal of every repo, code search,
    README/doc fetching, all file types
  - Synthetic generation (Claude produces prompt/completion pairs)

Stores collected data in JSONL format under the configured data/ directory.
No rate limiting, no filtering — collects aggressively.
"""

import concurrent.futures
import json
import time
from pathlib import Path
from urllib.parse import urljoin, urlparse

import anthropic
import requests
from bs4 import BeautifulSoup

from ghoul.config import CFG
from ghoul.memory import Memory


# File extensions considered collectible from GitHub repos
_CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".c", ".cpp", ".h",
    ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala", ".cs",
    ".sh", ".bash", ".zsh", ".pl", ".r", ".lua", ".zig", ".nim",
    ".ex", ".exs", ".hs", ".ml", ".clj", ".lisp", ".el",
}
_DOC_EXTENSIONS = {
    ".md", ".rst", ".txt", ".adoc", ".org", ".wiki", ".yaml", ".yml",
    ".toml", ".json", ".cfg", ".ini", ".conf",
}
_ALL_EXTENSIONS = _CODE_EXTENSIONS | _DOC_EXTENSIONS


# ---------------------------------------------------------------------------
# Web Scraping — deep crawl
# ---------------------------------------------------------------------------

def scrape_url(url: str) -> list[dict]:
    """
    Aggressively scrape all content from *url*.

    Extracts code blocks, paragraphs, headings, list items, table cells,
    definition lists, and blockquotes — capturing every piece of
    documentation and code on the page.

    Returns a list of dicts with keys: source, content, url, tag, scraped_at.
    """
    headers = {"User-Agent": "Mozilla/5.0 (compatible; GhoulBot/1.0)"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    samples: list[dict] = []
    ts = time.time()

    # 1. Code blocks (highest value)
    for tag in soup.find_all(["code", "pre", "samp", "kbd"]):
        text = tag.get_text(strip=True)
        if len(text) > 20:
            samples.append({
                "source": "web_scrape_code",
                "url": url,
                "tag": tag.name,
                "content": text,
                "scraped_at": ts,
            })

    # 2. Documentation text — paragraphs, headings, list items, blockquotes
    for tag in soup.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6",
                              "li", "dt", "dd", "blockquote", "figcaption"]):
        text = tag.get_text(strip=True)
        if len(text) > 30:
            samples.append({
                "source": "web_scrape_text",
                "url": url,
                "tag": tag.name,
                "content": text,
                "scraped_at": ts,
            })

    # 3. Tables (row-by-row)
    for table in soup.find_all("table"):
        for row in table.find_all("tr"):
            cells = [td.get_text(strip=True) for td in row.find_all(["td", "th"])]
            row_text = " | ".join(cells)
            if len(row_text) > 20:
                samples.append({
                    "source": "web_scrape_table",
                    "url": url,
                    "tag": "tr",
                    "content": row_text,
                    "scraped_at": ts,
                })

    # 4. Full-page text as a single document (captures anything missed above)
    full_text = soup.get_text(separator="\n", strip=True)
    if len(full_text) > 200:
        samples.append({
            "source": "web_scrape_full",
            "url": url,
            "tag": "body",
            "content": full_text,
            "scraped_at": ts,
        })

    return samples


def _discover_links(url: str, soup: BeautifulSoup, max_links: int = 50) -> list[str]:
    """
    Discover same-domain and documentation-like links on a page.

    Returns up to *max_links* absolute URLs worth following.
    """
    base_domain = urlparse(url).netloc
    found: list[str] = []
    seen: set[str] = set()

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        absolute = urljoin(url, href)
        parsed = urlparse(absolute)

        # Stay on the same domain or known doc hosts
        if parsed.netloc != base_domain:
            continue
        # Skip anchors, javascript, mailto
        if parsed.scheme not in ("http", "https"):
            continue
        # Deduplicate
        clean = parsed._replace(fragment="").geturl()
        if clean in seen:
            continue
        seen.add(clean)
        found.append(clean)

        if len(found) >= max_links:
            break

    return found


def scrape_deep(
    seed_urls: list[str],
    max_depth: int = 2,
    max_pages: int = 100,
) -> list[dict]:
    """
    Deep-crawl starting from *seed_urls*, following links up to *max_depth*.

    Scrapes every page encountered and returns all samples.
    """
    visited: set[str] = set()
    all_samples: list[dict] = []
    frontier: list[tuple[str, int]] = [(u, 0) for u in seed_urls]

    headers = {"User-Agent": "Mozilla/5.0 (compatible; GhoulBot/1.0)"}

    while frontier and len(visited) < max_pages:
        url, depth = frontier.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
        except Exception as exc:
            print(f"[DataCollector] Failed to fetch {url}: {exc}")
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # Scrape this page
        try:
            samples = scrape_url(url)
            all_samples.extend(samples)
        except Exception as exc:
            print(f"[DataCollector] Failed to scrape {url}: {exc}")

        # Discover and queue links for deeper crawling
        if depth < max_depth:
            links = _discover_links(url, soup)
            for link in links:
                if link not in visited:
                    frontier.append((link, depth + 1))

    print(f"[DataCollector] Deep-crawled {len(visited)} pages, "
          f"collected {len(all_samples)} samples.")
    return all_samples


def scrape_urls(urls: list[str]) -> list[dict]:
    """Scrape multiple URLs with deep crawling and aggregate results."""
    return scrape_deep(urls, max_depth=2, max_pages=100)


# ---------------------------------------------------------------------------
# GitHub API — exhaustive repository scraping
# ---------------------------------------------------------------------------

def _github_headers() -> dict[str, str]:
    """Build GitHub API request headers."""
    token = CFG.get("github_token", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_full_tree(full_name: str, headers: dict) -> list[dict]:
    """
    Fetch the *full recursive* file tree for a GitHub repository.

    Uses ``?recursive=1`` to get every file in the repo in a single call.
    """
    tree_url = (
        f"https://api.github.com/repos/{full_name}/git/trees/HEAD?recursive=1"
    )
    try:
        resp = requests.get(tree_url, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json().get("tree", [])
    except Exception:
        return []


def _fetch_raw_file(full_name: str, path: str, branch: str = "HEAD") -> str | None:
    """Download a single raw file from a GitHub repo."""
    raw_url = (
        f"https://raw.githubusercontent.com/{full_name}/{branch}/{path}"
    )
    try:
        resp = requests.get(raw_url, timeout=30)
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


def _fetch_readme(full_name: str, headers: dict) -> str | None:
    """Fetch the README contents for a repository."""
    url = f"https://api.github.com/repos/{full_name}/readme"
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        import base64
        data = resp.json()
        content = data.get("content", "")
        encoding = data.get("encoding", "base64")
        if encoding == "base64" and content:
            return base64.b64decode(content).decode("utf-8", errors="replace")
        return content
    except Exception:
        return None


def _scrape_single_repo(
    full_name: str,
    headers: dict,
    max_files: int = 200,
) -> list[dict]:
    """
    Scrape every collectible file from one GitHub repository.

    Fetches the full recursive tree, then downloads all code and
    documentation files up to *max_files*.
    """
    samples: list[dict] = []
    ts = time.time()

    # 1. README
    readme = _fetch_readme(full_name, headers)
    if readme:
        samples.append({
            "source": "github_readme",
            "repo": full_name,
            "path": "README",
            "content": readme,
            "fetched_at": ts,
        })

    # 2. Full recursive file tree
    tree = _fetch_full_tree(full_name, headers)
    fetched = 0

    for item in tree:
        if fetched >= max_files:
            break
        if item.get("type") != "blob":
            continue

        path = item.get("path", "")
        ext = "." + path.rsplit(".", 1)[-1] if "." in path else ""

        if ext.lower() not in _ALL_EXTENSIONS:
            continue

        content = _fetch_raw_file(full_name, path)
        if content is None:
            continue

        source_type = "github_code" if ext.lower() in _CODE_EXTENSIONS else "github_doc"
        samples.append({
            "source": source_type,
            "repo": full_name,
            "path": path,
            "content": content,
            "fetched_at": time.time(),
        })
        fetched += 1

    return samples


def search_github(
    query: str,
    max_repos: int = 100,
    max_files_per_repo: int = 200,
) -> list[dict]:
    """
    Search GitHub for repositories matching *query* and exhaustively
    scrape every code and documentation file from each repo.

    Also runs a GitHub code search to find additional relevant files
    across all of GitHub.

    Parameters
    ----------
    query:              Search query (e.g. ``"Python async programming"``).
    max_repos:          Maximum number of repositories to scrape.
    max_files_per_repo: Maximum files to download per repo.

    Returns
    -------
    List of sample dicts.
    """
    headers = _github_headers()
    all_samples: list[dict] = []

    # ------------------------------------------------------------------
    # 1. Repository search — fetch multiple pages to get more repos
    # ------------------------------------------------------------------
    search_url = "https://api.github.com/search/repositories"
    repos: list[dict] = []
    per_page = min(max_repos, 100)
    pages_needed = (max_repos + per_page - 1) // per_page

    for page in range(1, pages_needed + 1):
        params = {
            "q": query,
            "sort": "stars",
            "per_page": per_page,
            "page": page,
        }
        try:
            resp = requests.get(
                search_url, headers=headers, params=params, timeout=30,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
            repos.extend(items)
            if len(items) < per_page:
                break  # no more results
        except Exception as exc:
            print(f"[DataCollector] GitHub repo search page {page} failed: {exc}")
            break

    print(f"[DataCollector] Found {len(repos)} repos for '{query}'.")

    # ------------------------------------------------------------------
    # 2. Scrape every repo in parallel
    # ------------------------------------------------------------------
    def _scrape_repo(repo: dict) -> list[dict]:
        full_name = repo["full_name"]
        try:
            samples = _scrape_single_repo(
                full_name, headers, max_files=max_files_per_repo,
            )
            print(f"[DataCollector]   {full_name}: {len(samples)} files")
            return samples
        except Exception as exc:
            print(f"[DataCollector]   {full_name}: failed — {exc}")
            return []

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(_scrape_repo, repo) for repo in repos]
        for future in concurrent.futures.as_completed(futures):
            all_samples.extend(future.result())

    # ------------------------------------------------------------------
    # 3. GitHub code search — find additional relevant files across GitHub
    # ------------------------------------------------------------------
    code_samples = search_github_code(query, headers=headers)
    all_samples.extend(code_samples)

    return all_samples


def search_github_code(
    query: str,
    headers: dict | None = None,
    max_results: int = 100,
) -> list[dict]:
    """
    Use the GitHub code search API to find individual files matching *query*
    across all of GitHub.

    Parameters
    ----------
    query:       Code search query.
    headers:     GitHub API headers (optional; built from config if None).
    max_results: Maximum number of code results to fetch.

    Returns
    -------
    List of sample dicts.
    """
    headers = headers or _github_headers()
    search_url = "https://api.github.com/search/code"
    samples: list[dict] = []
    per_page = min(max_results, 100)
    pages_needed = (max_results + per_page - 1) // per_page

    for page in range(1, pages_needed + 1):
        params = {
            "q": query,
            "per_page": per_page,
            "page": page,
        }
        try:
            resp = requests.get(
                search_url, headers=headers, params=params, timeout=30,
            )
            resp.raise_for_status()
            items = resp.json().get("items", [])
        except Exception as exc:
            print(f"[DataCollector] GitHub code search page {page} failed: {exc}")
            break

        for item in items:
            repo_name = item.get("repository", {}).get("full_name", "unknown")
            path = item.get("path", "")
            html_url = item.get("html_url", "")

            # Fetch the raw file content
            content = _fetch_raw_file(repo_name, path)
            if content is None:
                continue

            samples.append({
                "source": "github_code_search",
                "repo": repo_name,
                "path": path,
                "html_url": html_url,
                "content": content,
                "fetched_at": time.time(),
            })

        if len(items) < per_page:
            break

    print(f"[DataCollector] GitHub code search returned {len(samples)} files.")
    return samples


# ---------------------------------------------------------------------------
# Synthetic Data Generation
# ---------------------------------------------------------------------------

_SYNTH_SYSTEM = """\
You are a training data generator for a Python coding AI.
Given a topic, generate distinct prompt/completion pairs as a JSON array:
[
  {"prompt": "...", "completion": "..."},
  ...
]
Each "prompt" is a detailed coding task and "completion" is the full,
production-quality Python solution with docstrings and error handling.
Cover beginner, intermediate, and advanced difficulty levels.
Return ONLY valid JSON — no markdown fences, no extra text.
"""


def generate_synthetic(topic: str, count: int = 20) -> list[dict]:
    """
    Use Claude to generate *count* synthetic prompt/completion pairs on *topic*.

    Makes multiple API calls in batches of 10 to maximize the number of
    high-quality examples produced.
    """
    client = anthropic.Anthropic(api_key=CFG["anthropic_api_key"])
    all_pairs: list[dict] = []
    batch_size = 10

    for batch_start in range(0, count, batch_size):
        batch_count = min(batch_size, count - batch_start)
        message = client.messages.create(
            model=CFG["model"],
            max_tokens=8192,
            system=_SYNTH_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"Generate {batch_count} Python coding prompt/completion "
                        f"pairs on the topic: {topic}. "
                        f"Make them diverse — cover different subtopics, "
                        f"difficulty levels, and coding patterns."
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
        batch_samples = [
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
        all_pairs.extend(batch_samples)

    return all_pairs


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
    synthetic_count: int = 20,
    max_repos: int = 100,
    max_files_per_repo: int = 200,
    crawl_depth: int = 2,
    crawl_max_pages: int = 100,
    memory: Memory | None = None,
) -> Path:
    """
    Collect training data on *topic* from all sources and save to JSONL.

    Scrapes every reachable GitHub repository, every piece of
    documentation, and generates synthetic data to maximize the
    amount of training material collected.

    Parameters
    ----------
    topic:              Topic label used to name the output file.
    urls:               Optional list of seed URLs to deep-crawl.
    github_query:       Optional GitHub search query (defaults to topic).
    synthetic_count:    Number of synthetic examples to generate.
    max_repos:          Maximum GitHub repos to scrape (default 100).
    max_files_per_repo: Maximum files per repo (default 200).
    crawl_depth:        Link-following depth for web scraping (default 2).
    crawl_max_pages:    Max pages to visit per crawl (default 100).
    memory:             Optional Memory instance to record the collection event.

    Returns
    -------
    Path to the JSONL file.
    """
    data_dir: Path = CFG["data_dir"]
    safe_topic = topic.replace(" ", "_").replace("/", "_")[:64]
    out_path = data_dir / f"training_{safe_topic}_{int(time.time())}.jsonl"

    all_samples: list[dict] = []

    # 1. Deep web scraping (with link following)
    if urls:
        print(f"[DataCollector] Deep-crawling {len(urls)} seed URL(s) "
              f"(depth={crawl_depth}, max_pages={crawl_max_pages})…")
        scraped = scrape_deep(
            urls, max_depth=crawl_depth, max_pages=crawl_max_pages,
        )
        all_samples.extend(scraped)
        print(f"[DataCollector] Web scraping collected {len(scraped)} samples.")

    # 2. Exhaustive GitHub scraping
    gq = github_query or topic
    print(f"[DataCollector] Exhaustive GitHub scrape for '{gq}' "
          f"(max_repos={max_repos}, max_files_per_repo={max_files_per_repo})…")
    try:
        github_samples = search_github(
            gq,
            max_repos=max_repos,
            max_files_per_repo=max_files_per_repo,
        )
        all_samples.extend(github_samples)
        print(f"[DataCollector] GitHub scraping collected "
              f"{len(github_samples)} samples.")
    except Exception as exc:
        print(f"[DataCollector] GitHub search failed: {exc}")

    # 3. Synthetic data generation (batched for volume)
    print(f"[DataCollector] Generating {synthetic_count} synthetic examples…")
    synth = generate_synthetic(topic, count=synthetic_count)
    all_samples.extend(synth)
    print(f"[DataCollector] Generated {len(synth)} synthetic samples.")

    # Save
    save_jsonl(all_samples, out_path)
    print(f"[DataCollector] Saved {len(all_samples)} total samples → {out_path}")

    if memory:
        memory.record_data_collection(
            source="web+github+github_code+synthetic",
            count=len(all_samples),
            path=str(out_path),
        )

    return out_path
