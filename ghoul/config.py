"""
ghoul/config.py — Configuration loader.

Loads configuration from environment variables and/or a config.yaml file.
"""

import os
from pathlib import Path

import yaml


# Default paths
_ROOT = Path(__file__).parent.parent
_CONFIG_FILE = _ROOT / "config.yaml"
_DATA_DIR = _ROOT / "data"


def _load_yaml(path: Path) -> dict:
    if path.exists():
        with open(path, "r") as f:
            return yaml.safe_load(f) or {}
    return {}


def load_config() -> dict:
    """Load configuration from environment variables and config.yaml."""
    yaml_cfg = _load_yaml(_CONFIG_FILE)

    config = {
        # Anthropic
        "anthropic_api_key": os.environ.get(
            "ANTHROPIC_API_KEY", yaml_cfg.get("anthropic_api_key", "")
        ),
        "model": os.environ.get(
            "GHOUL_MODEL", yaml_cfg.get("model", "claude-sonnet-4-20250514")
        ),
        # GitHub (optional — used by data_collector)
        "github_token": os.environ.get(
            "GITHUB_TOKEN", yaml_cfg.get("github_token", "")
        ),
        # Storage
        "data_dir": Path(
            os.environ.get("GHOUL_DATA_DIR", yaml_cfg.get("data_dir", str(_DATA_DIR)))
        ),
        # Fine-tuning (HuggingFace)
        "hf_token": os.environ.get("HF_TOKEN", yaml_cfg.get("hf_token", "")),
        "hf_model_name": os.environ.get(
            "HF_MODEL_NAME", yaml_cfg.get("hf_model_name", "")
        ),
    }

    # Ensure data directory exists
    config["data_dir"].mkdir(parents=True, exist_ok=True)

    return config


# Module-level singleton so callers can do `from ghoul.config import CFG`
CFG = load_config()
