from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------
# Storage location (legacy defaults)
# ---------------------------------------------------------------------

GRAPH_CACHE_DIR = Path(__file__).resolve().parent / ".cache"
GRAPH_CACHE_DIR.mkdir(exist_ok=True)

MERGED_GRAPH_PATH = GRAPH_CACHE_DIR / "merged_pedigree_graph.json"

# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _try_get_flattened_cache_dir() -> Path | None:
    """
    Best-effort import of the flattened pedigree cache directory.

    We keep this import local/optional to avoid hard coupling or circular imports.
    """
    try:
        from .pedigree_store import DEFAULT_CACHE_DIR  # type: ignore
    except Exception:
        return None
    return Path(DEFAULT_CACHE_DIR)


def _compute_source_max_mtime(source_dir: Path) -> float | None:
    """
    Return the maximum mtime (seconds) across JSON files in source_dir, or None if no files.
    """
    if not source_dir.exists() or not source_dir.is_dir():
        return None

    max_mtime: float | None = None
    for p in source_dir.glob("*.json"):
        try:
            m = p.stat().st_mtime
        except OSError:
            continue
        if max_mtime is None or m > max_mtime:
            max_mtime = m

    return max_mtime


# ---------------------------------------------------------------------
# New persistence API (cache_dir-driven, schema'd)
# ---------------------------------------------------------------------


def get_default_merged_graph_path(cache_dir: Path) -> Path:
    """
    Return the default merged-graph path within the given cache_dir.
    """
    return Path(cache_dir) / "merged_pedigree_graph.json"


def save_merged_pedigree_graph(
    graph: dict[int, dict[str, Any]],
    cache_dir: Path,
    path: Path | None = None,
) -> None:
    """
    Persist the merged pedigree graph to disk (JSON).

    - Keys are converted to strings for JSON.
    - Writes to a temporary file and atomically replaces the target.
    - Stores minimal metadata for future schema evolution.

    Staleness metadata:
      - If the flattened pedigree cache directory is available, stores
        source_max_mtime = max mtime of *.json in DEFAULT_CACHE_DIR.
    """
    target_path = Path(path) if path is not None else get_default_merged_graph_path(cache_dir)
    target_path.parent.mkdir(parents=True, exist_ok=True)

    tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")

    # Convert int keys to str for JSON
    serializable_graph: dict[str, dict[str, Any]] = {str(k): v for k, v in graph.items()}

    source_cache_dir = _try_get_flattened_cache_dir()
    source_max_mtime = _compute_source_max_mtime(source_cache_dir) if source_cache_dir else None

    payload: dict[str, Any] = {
        "schema_version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "node_count": len(graph),
        "graph": serializable_graph,
    }

    # Only include if we could compute it (keeps older files/loaders sane)
    if source_max_mtime is not None:
        payload["source_max_mtime"] = source_max_mtime
        payload["source_cache_dir"] = str(source_cache_dir) if source_cache_dir else None

    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Atomic replace
    tmp_path.replace(target_path)


def load_merged_pedigree_graph(
    cache_dir: Path,
    path: Path | None = None,
) -> dict[int, dict[str, Any]]:
    """
    Load merged pedigree graph from disk (JSON).

    Raises:
      - FileNotFoundError if the file does not exist
      - ValueError if the file is malformed or has an unsupported schema
      - json.JSONDecodeError for invalid JSON

    Staleness behavior:
      - If the file includes source_max_mtime and we can compute the current
        max mtime of *.json in DEFAULT_CACHE_DIR, then:
          - if current_source_max_mtime > stored_source_max_mtime, raise ValueError
            to signal that the merged graph is stale.
    """
    target_path = Path(path) if path is not None else get_default_merged_graph_path(cache_dir)

    if not target_path.exists():
        raise FileNotFoundError(f"Merged graph not found: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    schema_version = payload.get("schema_version")
    if schema_version != 1:
        raise ValueError(f"Unsupported merged graph schema_version: {schema_version}")

    # ---- staleness detection (best effort) ----
    stored_source_max_mtime = payload.get("source_max_mtime")
    if isinstance(stored_source_max_mtime, (int, float)):
        source_cache_dir = _try_get_flattened_cache_dir()
        if source_cache_dir is not None:
            current_source_max_mtime = _compute_source_max_mtime(source_cache_dir)
            if isinstance(current_source_max_mtime, (int, float)):
                # If any source file is newer than what this merged graph was built from, it's stale.
                if current_source_max_mtime > float(stored_source_max_mtime):
                    raise ValueError(
                        "Merged graph is stale (flattened pedigree cache has newer files)."
                    )

    graph_raw = payload.get("graph")
    if not isinstance(graph_raw, dict):
        raise ValueError("Malformed merged graph payload: 'graph' must be an object")

    graph: dict[int, dict[str, Any]] = {}
    for k, v in graph_raw.items():
        try:
            kid = int(k)
        except Exception as e:
            raise ValueError(f"Malformed merged graph key (expected int-like): {k!r}") from e
        if not isinstance(v, dict):
            raise ValueError(f"Malformed merged graph node for id {k!r}: expected object, got {type(v)}")
        graph[kid] = v

    return graph


# ---------------------------------------------------------------------
# Legacy API (backwards compatible wrappers)
# ---------------------------------------------------------------------


def save_merged_graph(graph: dict[int, dict[str, Any]]) -> None:
    """
    Persist the merged pedigree graph to disk.

    Legacy wrapper around save_merged_pedigree_graph().
    """
    save_merged_pedigree_graph(graph=graph, cache_dir=GRAPH_CACHE_DIR, path=MERGED_GRAPH_PATH)


def load_merged_graph() -> dict[int, dict[str, Any]] | None:
    """
    Load merged pedigree graph from disk if present.

    Legacy behavior:
      - returns None if missing
      - returns None (and prints warning) if load fails or is stale
    """
    if not MERGED_GRAPH_PATH.exists():
        return None

    try:
        return load_merged_pedigree_graph(cache_dir=GRAPH_CACHE_DIR, path=MERGED_GRAPH_PATH)
    except Exception as e:
        print("[graph-store] WARNING: failed to load merged graph:", e)
        return None


def delete_merged_graph() -> None:
    """
    Delete persisted merged graph.
    """
    if MERGED_GRAPH_PATH.exists():
        MERGED_GRAPH_PATH.unlink()