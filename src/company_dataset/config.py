from __future__ import annotations

from pathlib import Path

RAW_DIR_NAME = "raw"
CACHE_DIR_NAME = "cache"
INTERMEDIATE_DIR_NAME = "intermediate"
OUTPUT_DIR_NAME = "output"
REPORTS_DIR_NAME = "reports"

DEFAULT_DATA_DIR = "data"


def resolve_dirs(data_dir: str | Path = DEFAULT_DATA_DIR) -> dict[str, Path]:
    base = Path(data_dir)
    dirs = {
        "data": base,
        "raw": base / RAW_DIR_NAME,
        "cache": base / CACHE_DIR_NAME,
        "intermediate": base / INTERMEDIATE_DIR_NAME,
        "output": base / OUTPUT_DIR_NAME,
        "reports": Path(REPORTS_DIR_NAME),
    }
    for key, path in dirs.items():
        path.mkdir(parents=True, exist_ok=True)
    return dirs
