from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# Default cache directory (relative to project root)
DEFAULT_CACHE_DIR = Path(".cache") / "pedigrees"


def _cache_path(horse_id: int, cache_dir: Path = DEFAULT_CACHE_DIR) -> Path:
    # One file per horse id
    return cache_dir / f"{horse_id}.json"


def load_flat_pedigree(horse_id: int) -> Optional[list[dict]]:
    """
    Return cached flattened pedigree if present, else None.
    """
    path = _cache_path(horse_id)
    if not path.exists():
        return None

    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        # If cache is corrupted, treat as miss (and let pipeline rebuild)
        return None

    # Validate basic structure
    if not isinstance(data, list):
        return None
    if data and not isinstance(data[0], dict):
        return None

    return data


def save_flat_pedigree(horse_id: int, flat: list[dict]) -> None:
    """
    Persist flattened pedigree locally.
    """
    path = _cache_path(horse_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    # Write atomically to avoid partial files on crash
    tmp_path = path.with_suffix(".json.tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(flat, f, ensure_ascii=False, indent=2)

    tmp_path.replace(path)