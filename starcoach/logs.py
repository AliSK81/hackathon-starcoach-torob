"""Append-only JSONL event log. One file per stream, one JSON object per line."""

import json
from datetime import datetime, timezone
from pathlib import Path

SECRET_KEYS = {"api_key", "llm_api_key", "authorization", "password", "token"}


def _redact(fields: dict) -> dict:
    return {k: ("***" if k.lower() in SECRET_KEYS else v) for k, v in fields.items()}


def log_event(log_dir: Path, stream: str, event: str, **fields) -> dict:
    """Append one event to `<log_dir>/<stream>.jsonl` and return the record."""
    record = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **_redact(fields)}
    log_dir.mkdir(parents=True, exist_ok=True)
    with open(log_dir / f"{stream}.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
    return record
