from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any


def repo_root_from_config(config_path: str | Path) -> Path:
    """Infer the repository root from a config file path.

    The default project config lives in ``configs/project.toml``. Inferring paths this
    way keeps scripts runnable both through Poetry entry points and direct execution.
    """

    path = Path(config_path).expanduser().resolve()
    if path.parent.name == "configs":
        return path.parent.parent
    return Path.cwd().resolve()


def load_config(config_path: str | Path = "configs/project.toml") -> dict[str, Any]:
    """Load TOML configuration and attach resolved project paths."""

    path = Path(config_path).expanduser().resolve()
    with path.open("rb") as fh:
        config: dict[str, Any] = tomllib.load(fh)

    root = repo_root_from_config(path)
    config["_config_path"] = str(path)
    config["_repo_root"] = str(root)
    resolved_paths: dict[str, str] = {}
    for key, value in config.get("paths", {}).items():
        raw_path = Path(value)
        resolved_paths[key] = str(raw_path if raw_path.is_absolute() else root / raw_path)
    config["resolved_paths"] = resolved_paths
    return config


def path_from_config(config: dict[str, Any], key: str) -> Path:
    """Return a resolved path from the loaded config."""

    try:
        return Path(config["resolved_paths"][key])
    except KeyError as exc:
        raise KeyError(f"Missing configured path: {key}") from exc


def ensure_output_directories(config: dict[str, Any]) -> None:
    """Create all configured derived-output directories."""

    for key in ("processed_data", "tables", "figures", "reports"):
        path_from_config(config, key).mkdir(parents=True, exist_ok=True)
