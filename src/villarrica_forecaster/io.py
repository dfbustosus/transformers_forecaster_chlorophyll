from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


def write_csv(df: pd.DataFrame, path: str | Path) -> Path:
    """Write a dataframe as CSV with parent-directory creation."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output, index=False)
    return output


def write_json(data: dict[str, Any], path: str | Path) -> Path:
    """Write a JSON file with stable formatting."""

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False, sort_keys=True)
        fh.write("\n")
    return output


def utc_now_iso() -> str:
    """Return an ISO-8601 UTC timestamp for reproducibility metadata."""

    return datetime.now(UTC).replace(microsecond=0).isoformat()


def relative_to_root(path: str | Path, root: str | Path) -> str:
    """Return a repository-relative path when possible."""

    candidate = Path(path).resolve()
    root_path = Path(root).resolve()
    try:
        return candidate.relative_to(root_path).as_posix()
    except ValueError:
        return candidate.as_posix()
