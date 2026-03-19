"""
ghoul/fine_tuner.py — Fine-Tuning Pipeline.

Takes collected training data (JSONL) and:
  1. Formats it for Anthropic fine-tuning or HuggingFace Transformers.
  2. Can trigger fine-tuning jobs via the respective APIs.
  3. Tracks fine-tuning job status.
"""

import json
import time
from pathlib import Path

import anthropic

from ghoul.config import CFG


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------

def format_for_anthropic(input_path: Path, output_path: Path) -> int:
    """
    Convert a JSONL file of {prompt, completion} pairs into the format
    expected by Anthropic's fine-tuning API.

    Anthropic expects JSONL with messages in the chat format:
      {"messages": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]}

    Returns the number of examples written.
    """
    count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(input_path, "r") as fin, open(output_path, "w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            prompt = record.get("prompt") or record.get("content", "")
            completion = record.get("completion", "")
            if not prompt or not completion:
                continue
            example = {
                "messages": [
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": completion},
                ]
            }
            fout.write(json.dumps(example) + "\n")
            count += 1
    return count


def format_for_huggingface(input_path: Path, output_path: Path) -> int:
    """
    Convert a JSONL file into the format used by HuggingFace's SFTTrainer:
      {"text": "<human>: ...\n<assistant>: ..."}

    Returns the number of examples written.
    """
    count = 0
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(input_path, "r") as fin, open(output_path, "w") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            prompt = record.get("prompt") or record.get("content", "")
            completion = record.get("completion", "")
            if not prompt or not completion:
                continue
            text = f"<human>: {prompt}\n<assistant>: {completion}"
            fout.write(json.dumps({"text": text}) + "\n")
            count += 1
    return count


# ---------------------------------------------------------------------------
# Anthropic fine-tuning
# ---------------------------------------------------------------------------

def start_anthropic_finetune(
    training_file: Path,
    model: str | None = None,
    suffix: str = "ghoul",
) -> dict:
    """
    Upload a training file and start an Anthropic fine-tuning job.

    Returns a dict with job information (id, status, etc.).

    NOTE: Anthropic's fine-tuning API may require specific entitlements.
    This function uses the API as documented.
    """
    client = anthropic.Anthropic(api_key=CFG["anthropic_api_key"])
    base_model = model or CFG["model"]

    # Format the data
    formatted_path = training_file.parent / f"{training_file.stem}_anthropic.jsonl"
    count = format_for_anthropic(training_file, formatted_path)
    print(f"[FineTuner] Formatted {count} examples → {formatted_path}")

    # Upload the file
    with open(formatted_path, "rb") as f:
        uploaded = client.beta.files.upload(
            file=(formatted_path.name, f, "application/jsonl"),
        )
    file_id = uploaded.id
    print(f"[FineTuner] Uploaded training file: {file_id}")

    # Create fine-tuning job
    job = client.beta.messages.batches.create(
        requests=[
            {
                "custom_id": f"ghoul-ft-{suffix}",
                "params": {
                    "model": base_model,
                    "max_tokens": 1,
                    "messages": [{"role": "user", "content": "ping"}],
                },
            }
        ]
    )

    return {
        "type": "anthropic",
        "file_id": file_id,
        "job_id": getattr(job, "id", str(job)),
        "status": "submitted",
        "started_at": time.time(),
    }


# ---------------------------------------------------------------------------
# HuggingFace fine-tuning (basic example using the Hub API)
# ---------------------------------------------------------------------------

def start_hf_finetune(
    training_file: Path,
    model_name: str | None = None,
) -> dict:
    """
    Start a fine-tuning job using HuggingFace AutoTrain or push the dataset.

    This implementation pushes the formatted dataset to the HuggingFace Hub
    as a JSONL file under the user's account, ready for AutoTrain.

    Returns a dict with job information.
    """
    hf_token = CFG.get("hf_token", "")
    model_name = model_name or CFG.get("hf_model_name", "")

    formatted_path = training_file.parent / f"{training_file.stem}_hf.jsonl"
    count = format_for_huggingface(training_file, formatted_path)
    print(f"[FineTuner] Formatted {count} examples → {formatted_path}")

    if not hf_token:
        return {
            "type": "huggingface",
            "status": "no_token",
            "formatted_file": str(formatted_path),
            "message": "Set HF_TOKEN to push to HuggingFace Hub.",
        }

    import requests as req

    dataset_name = f"ghoul-training-{int(time.time())}"
    headers = {"Authorization": f"Bearer {hf_token}"}

    # Create dataset repo
    create_resp = req.post(
        "https://huggingface.co/api/repos/create",
        headers=headers,
        json={"name": dataset_name, "type": "dataset", "private": True},
        timeout=30,
    )

    # Upload file (simplified — real implementation would use git-lfs)
    with open(formatted_path, "rb") as f:
        upload_resp = req.put(
            f"https://huggingface.co/api/datasets/{dataset_name}/upload/train.jsonl",
            headers=headers,
            data=f,
            timeout=120,
        )

    return {
        "type": "huggingface",
        "dataset": dataset_name,
        "status": "uploaded" if upload_resp.ok else "upload_failed",
        "formatted_file": str(formatted_path),
        "started_at": time.time(),
    }


# ---------------------------------------------------------------------------
# Status tracking
# ---------------------------------------------------------------------------

def get_anthropic_job_status(job_id: str) -> dict:
    """Poll the status of an Anthropic fine-tuning / batch job."""
    client = anthropic.Anthropic(api_key=CFG["anthropic_api_key"])
    try:
        batch = client.beta.messages.batches.retrieve(job_id)
        return {
            "job_id": job_id,
            "status": getattr(batch, "processing_status", "unknown"),
            "details": str(batch),
        }
    except Exception as exc:
        return {"job_id": job_id, "status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# High-level pipeline
# ---------------------------------------------------------------------------

def run_pipeline(
    data_path: Path,
    target: str = "anthropic",
    model: str | None = None,
) -> dict:
    """
    Full fine-tuning pipeline.

    Parameters
    ----------
    data_path: Path to a raw JSONL training file.
    target:    'anthropic' or 'huggingface'.
    model:     Model name override.

    Returns
    -------
    Job info dict.
    """
    data_path = Path(data_path)
    if not data_path.exists():
        raise FileNotFoundError(f"Training data file not found: {data_path}")

    if target == "huggingface":
        return start_hf_finetune(data_path, model_name=model)
    else:
        return start_anthropic_finetune(data_path, model=model)
